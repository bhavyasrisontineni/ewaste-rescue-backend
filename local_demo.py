"""Local web adapter for E-Waste Rescue.

Keeps the existing lambda_function.py and ai_classifier.py unchanged.
The health and disposal-guide endpoints invoke the existing Lambda handler.
Image classification uses the existing CLIP classifier and saves scan history
locally because this workshop role cannot create the required AWS resources.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Set harmless defaults before importing the Lambda module. Local demo does not
# make AWS requests; its cloud-backed routes are replaced by local equivalents.
os.environ.setdefault("UPLOAD_BUCKET", "local-demo-bucket")
os.environ.setdefault("SCAN_TABLE", "LocalDemoScans")
os.environ.setdefault("CORS_ORIGIN", "http://127.0.0.1:5000")

from flask import Flask, jsonify, render_template, request
from ai_classifier import classify_image_bytes
from lambda_function import lambda_handler

app = Flask(__name__)
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "local_demo_data"
UPLOAD_DIR = DATA_DIR / "uploads"
HISTORY_FILE = DATA_DIR / "scan_history.json"
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_history():
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def save_history(items):
    HISTORY_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")


def invoke_lambda(method, path, body=None):
    """Invoke the existing Lambda handler with an API Gateway v2-shaped event."""
    event = {
        "version": "2.0",
        "rawPath": path,
        "requestContext": {"http": {"method": method}},
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }
    result = lambda_handler(event, None)
    return result


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/health")
def health():
    # The health route is served by the existing Lambda handler.
    result = invoke_lambda("GET", "/health")
    return (result.get("body", "{}"), result.get("statusCode", 200),
            {"Content-Type": "application/json"})


@app.get("/api/disposal-guide/<category>")
def disposal_guide(category):
    # The disposal guide is served by the existing Lambda handler.
    result = invoke_lambda("GET", f"/disposal-guide/{category}")
    return (result.get("body", "{}"), result.get("statusCode", 200),
            {"Content-Type": "application/json"})


@app.post("/api/classify")
def classify():
    uploaded = request.files.get("image")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Choose an image first."}), 400

    extension = Path(uploaded.filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        return jsonify({"error": "Use a JPG, PNG, or WEBP image."}), 400

    image_bytes = uploaded.read(MAX_UPLOAD_BYTES + 1)
    if not image_bytes:
        return jsonify({"error": "The selected file is empty."}), 400
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        return jsonify({"error": "Image must be 8 MB or smaller."}), 413

    try:
        prediction = classify_image_bytes(image_bytes)
    except Exception as exc:
        # Avoid exposing stack traces to the browser.
        app.logger.exception("Image classification failed")
        return jsonify({
            "error": "The image could not be classified. Check that it is a valid image and that the model dependencies are installed.",
            "detail": str(exc)[:240]
        }), 422

    scan_id = str(uuid.uuid4())
    stored_name = f"{scan_id}{extension}"
    (UPLOAD_DIR / stored_name).write_bytes(image_bytes)

    guide_result = invoke_lambda("GET", f"/disposal-guide/{prediction['category']}")
    try:
        guide_payload = json.loads(guide_result.get("body", "{}"))
    except json.JSONDecodeError:
        guide_payload = {}

    record = {
        "scanId": scan_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "filename": Path(uploaded.filename).name,
        "localImage": f"local_demo_data/uploads/{stored_name}",
        "category": prediction["category"],
        "confidence": prediction.get("confidence"),
        "modelStatus": prediction.get("model_status", "unknown"),
    }
    history = load_history()
    history.insert(0, record)
    save_history(history[:100])

    return jsonify({
        "scanId": scan_id,
        "prediction": prediction,
        "disposalGuide": {
            "title": guide_payload.get("title", prediction["category"].replace("_", " ").title()),
            "guidance": guide_payload.get("guidance", [
                "Keep the item out of household recycling until local guidance is confirmed.",
                "Do not burn or dismantle the item.",
                "Use an authorized e-waste collection point."
            ])
        },
        "stored": True,
        "storageMode": "local file (demo only)"
    })


@app.get("/api/history")
def history():
    return jsonify({"items": load_history(), "storageMode": "local file (demo only)"})


@app.post("/api/history/clear")
def clear_history():
    save_history([])
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("\nE-Waste Rescue local demo")
    print("Open http://127.0.0.1:5000 in your browser.")
    print("Images and scan history are stored locally in local_demo_data/.")
    app.run(host="127.0.0.1", port=5000, debug=False)
