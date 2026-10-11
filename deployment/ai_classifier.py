
from transformers import pipeline
from PIL import Image
from pathlib import Path

MODEL_NAME = "openai/clip-vit-base-patch32"

CANDIDATES = {
    "mobile_phone": "a photo of a mobile phone",
    "battery": "a photo of a battery",
    "charger_or_cable": "a photo of a charger or USB cable",
    "laptop_or_computer": "a photo of a laptop or desktop computer",
    "monitor_or_screen": "a photo of a computer monitor",
    "keyboard_or_mouse": "a photo of a keyboard or computer mouse",
    "earphones_or_headphones": "a photo of earphones or headphones",
    "printer_or_scanner": "a photo of a printer or scanner",
    "circuit_board": "a photo of an electronic circuit board",
    "other_e_waste": "a photo of another electronic waste item",
}

_classifier = None


def get_classifier():
    global _classifier

    if _classifier is None:
        _classifier = pipeline(
            task="zero-shot-image-classification",
            model=MODEL_NAME
        )

    return _classifier


def classify_image(image_path):
    path = Path(image_path)

    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {path}")

    with Image.open(path) as image:
        image = image.convert("RGB")
        results = get_classifier()(
            image,
            candidate_labels=list(CANDIDATES.values())
        )

    best = results[0]
    matched_category = next(
        category
        for category, label in CANDIDATES.items()
        if label == best["label"]
    )

    confidence = float(best["score"])

    return {
        "category": matched_category,
        "confidence": round(confidence, 4),
        "model_status": "pretrained_zero_shot",
        "notice": (
            "Prediction from a general-purpose pretrained model; "
            "not specifically trained or validated for e-waste."
        )
    }

def classify_image_bytes(image_bytes):
    """Classify an image supplied as bytes."""
    from io import BytesIO
    from PIL import Image

    with Image.open(BytesIO(image_bytes)) as image:
        image = image.convert("RGB")
        results = get_classifier()(
            image,
            candidate_labels=list(CANDIDATES.values())
        )

    best = results[0]
    category = next(
        key for key, label in CANDIDATES.items()
        if label == best["label"]
    )

    return {
        "category": category,
        "confidence": round(float(best["score"]), 4),
        "model_status": "pretrained_zero_shot",
        "notice": (
            "General-purpose model prediction; "
            "not specifically validated for e-waste."
        )
    }



if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Classify an electronic waste image."
    )
    parser.add_argument("image_path", help="Path to a local image file")
    args = parser.parse_args()

    try:
        print(json.dumps(classify_image(args.image_path), indent=2))
    except Exception as exc:
        raise SystemExit(f"Classification failed: {exc}")