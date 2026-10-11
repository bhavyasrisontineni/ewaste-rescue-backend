import json
import os
import uuid
import mimetypes
from datetime import datetime, timezone
from urllib.parse import unquote
from ai_classifier import classify_image_bytes

import boto3
from botocore.exceptions import ClientError

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

BUCKET_NAME = os.environ["UPLOAD_BUCKET"]
TABLE_NAME = os.environ["SCAN_TABLE"]
table = dynamodb.Table(TABLE_NAME)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024

DISPOSAL_GUIDES = {
    "mobile_phone": {
        "title": "Mobile phone",
        "guidance": [
            "Back up and erase personal data before recycling.",
            "Do not place the phone in household waste.",
            "Use an authorized e-waste collection point or take-back program."
        ]
    },
    "battery": {
        "title": "Battery",
        "guidance": [
            "Do not put batteries in household waste or regular recycling bins.",
            "Keep terminals from touching metal objects; do not puncture or crush the battery.",
            "Take it to an approved battery collection point."
        ]
    },
    "charger_or_cable": {
        "title": "Charger or cable",
        "guidance": [
            "Keep the item dry and do not use damaged electrical accessories.",
            "Take it to an e-waste collection point or electronics take-back program."
        ]
    },
    "laptop_or_computer": {
        "title": "Laptop or computer",
        "guidance": [
            "Back up and erase personal data before recycling.",
            "Remove accessories and follow the collection center's instructions.",
            "Use an authorized e-waste recycler."
        ]
    },
    "other_e_waste": {
        "title": "Other electronic waste",
        "guidance": [
            "Do not burn, dismantle, or place electronic waste in household waste.",
            "Use an authorized e-waste collection point and follow its instructions."
        ]
    },
    "monitor_or_screen": {
        "title": "Monitor or screen",
        "guidance": [
            "Do not place monitors or screens in household waste.",
            "Avoid breaking the screen or dismantling the device.",
            "Take it to an authorized electronics recycler."
        ]
    },
    "keyboard_or_mouse": {
        "title": "Keyboard or mouse",
        "guidance": [
            "Separate batteries if they are removable and follow local battery disposal guidance.",
            "Do not place electronic accessories in household waste.",
            "Take them to an authorized e-waste collection point."
        ]
    },
    "earphones_or_headphones": {
        "title": "Earphones or headphones",
        "guidance": [
            "Check whether the item contains a rechargeable battery.",
            "Do not burn or dismantle the device.",
            "Use an authorized e-waste collection point."
        ]
    },
    "printer_or_scanner": {
        "title": "Printer or scanner",
        "guidance": [
            "Remove paper and follow the manufacturer's recycling instructions.",
            "Handle ink or toner cartridges according to local collection guidance.",
            "Take the device to an authorized electronics recycler."
        ]
    },
    "circuit_board": {
        "title": "Circuit board",
        "guidance": [
            "Do not burn or chemically process circuit boards.",
            "Avoid dismantling components without appropriate training.",
            "Use an authorized e-waste recycler."
        ]
    }
}

def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": os.environ.get("CORS_ORIGIN", "*"),
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
        },
        "body": json.dumps(body)
    }

def parse_body(event):
    body = event.get("body")
    if not body:
        return {}
    if event.get("isBase64Encoded"):
        raise ValueError("Send JSON in the request body; upload image bytes directly to the presigned S3 URL.")
    return json.loads(body) if isinstance(body, str) else body


def classify_placeholder(filename=""):
    """
    DEMO ONLY: classifies using filename keywords.
    This does not inspect image pixels.
    """
    name = filename.lower().replace("-", "_").replace(" ", "_")

    if any(word in name for word in ("battery", "cell", "powerbank", "power_bank")):
        category = "battery"
    elif any(word in name for word in ("phone", "mobile", "smartphone")):
        category = "mobile_phone"
    elif any(word in name for word in ("laptop", "computer", "notebook", "desktop")):
        category = "laptop_or_computer"
    elif any(word in name for word in ("charger", "cable", "wire", "usb")):
        category = "charger_or_cable"
    elif any(word in name for word in ("monitor", "screen", "display")):
        category = "monitor_or_screen"
    elif any(word in name for word in ("keyboard", "mouse")):
        category = "keyboard_or_mouse"
    elif any(word in name for word in ("earphone", "headphone", "earbud")):
        category = "earphones_or_headphones"
    elif any(word in name for word in ("printer", "scanner")):
        category = "printer_or_scanner"
    elif any(word in name for word in ("circuit_board", "motherboard", "pcb")):
        category = "circuit_board"
    else:
        category = "other_e_waste"

    return {
        "category": category,
        "confidence": None,
        "model_status": "placeholder",
        "notice": "Demo classification based on filename only; it does not inspect the image."
    }

def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method")
    path = event.get("rawPath") or event.get("path") or "/"
    path = unquote(path)

    if method == "OPTIONS":
        return response(200, {"ok": True})

    if method == "GET" and path.endswith("/health"):
        return response(200, {"status": "ok", "service": "ewaste-rescue-backend"})

    if method == "GET" and "/disposal-guide/" in path:
        category = path.rstrip("/").split("/")[-1]
        guide = DISPOSAL_GUIDES.get(category)
        if not guide:
            return response(404, {"error": "Unknown category", "available_categories": list(DISPOSAL_GUIDES)})
        return response(200, {"category": category, **guide})

    if method == "POST" and path.endswith("/upload-url"):
        try:
            body = parse_body(event)
            filename = str(body.get("filename", "upload.jpg")).split("/")[-1]
            content_type = body.get("contentType", mimetypes.guess_type(filename)[0] or "")
            if content_type not in ALLOWED_TYPES:
                return response(400, {"error": "Unsupported image type. Use JPEG, PNG, or WEBP."})
            try:
                size = int(body.get("sizeBytes", 0))
            except (TypeError, ValueError):
                return response(400, {"error": "sizeBytes must be a number."})
            if size < 1 or size > MAX_UPLOAD_BYTES:
                return response(400, {"error": "Image must be between 1 byte and 8 MB."})

            scan_id = str(uuid.uuid4())
            key = f"uploads/{scan_id}/{filename}"
            url = s3.generate_presigned_url(
                "put_object",
                Params={"Bucket": BUCKET_NAME, "Key": key, "ContentType": content_type},
                ExpiresIn=300
            )
            return response(200, {
                "scanId": scan_id,
                "uploadUrl": url,
                "s3Key": key,
                "contentType": content_type,
                "expiresInSeconds": 300
            })
        except (ValueError, json.JSONDecodeError):
            return response(400, {"error": "Invalid JSON request body."})
        except ClientError:
            return response(500, {"error": "Could not create upload URL."})

    if method == "POST" and path.endswith("/classify"):
        try:
            body = parse_body(event)
            s3_key = body.get("s3Key")
            scan_id = body.get("scanId") or str(uuid.uuid4())
            if not isinstance(s3_key, str) or not s3_key.startswith("uploads/"):
                return response(400, {"error": "Provide the s3Key returned by /upload-url."})

            # Verify the uploaded object exists and obtain its metadata.
            try:
                obj = s3.head_object(Bucket=BUCKET_NAME, Key=s3_key)
            except ClientError:
                return response(400, {"error": "Image not found in storage. Upload it first."})

            content_type = obj.get("ContentType", "")
            if content_type not in ALLOWED_TYPES:
                return response(400, {"error": "Stored file is not a supported image type."})
            if obj.get("ContentLength", 0) > MAX_UPLOAD_BYTES:
                return response(400, {"error": "Image exceeds the 8 MB limit."})

            
            # Read the actual image from S3 and classify its contents.
            image_obj = s3.get_object(
                Bucket=BUCKET_NAME,
                Key=s3_key
            )
            image_bytes = image_obj["Body"].read()

            prediction = classify_image_bytes(image_bytes)
            category = prediction["category"]
            item = {
                "scanId": scan_id,
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "s3Key": s3_key,
                "category": category,
                "modelStatus": prediction["model_status"]
            }
            table.put_item(Item=item)
            return response(200, {
                "scanId": scan_id,
                "prediction": prediction,
                "disposalGuide": DISPOSAL_GUIDES[category],
                "stored": True
            })
        except (ValueError, json.JSONDecodeError):
            return response(400, {"error": "Invalid JSON request body."})
        except ClientError:
            return response(500, {"error": "Could not save or process this scan."})

    return response(404, {"error": "Route not found", "path": path, "method": method})
