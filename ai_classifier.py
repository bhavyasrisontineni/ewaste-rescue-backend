
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

NON_E_WASTE_CANDIDATES = {
    "flower": "a photo of a flower or plant",
    "book": "a photo of a book or notebook",
    "food": "a photo of food",
    "clothing": "a photo of clothing or shoes",
    "animal": "a photo of an animal",
    "person": "a photo of a person",
    "landscape": "a photo of an outdoor landscape",
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


def classify_image_content(image):
    image = image.convert("RGB")

    all_candidates = {**CANDIDATES, **NON_E_WASTE_CANDIDATES}
    results = get_classifier()(
        image,
        candidate_labels=list(all_candidates.values())
    )

    if not results:
        return {
            "category": "uncertain",
            "confidence": 0.0,
            "model_status": "no_prediction",
            "notice": "No reliable prediction was returned. Please try another image."
        }

    best = results[0]
    matched_category = next(
        category for category, label in all_candidates.items()
        if label == best["label"]
    )
    confidence = float(best["score"])

    # Similarity scores are not calibrated probabilities.
    # These thresholds are initial demo safeguards, not validated guarantees.
    if matched_category in NON_E_WASTE_CANDIDATES:
        return {
            "category": "not_e_waste",
            "confidence": round(confidence, 4),
            "model_status": "possible_non_e_waste",
            "notice": (
                "This image may not show electronic waste. "
                "Upload a clear photo of an electronic item."
            )
        }

    if confidence < 0.30:
        return {
            "category": "uncertain",
            "confidence": round(confidence, 4),
            "model_status": "low_confidence",
            "notice": (
                "The AI could not identify this item reliably. "
                "Try a clearer photo and verify the item manually."
            )
        }

    return {
        "category": matched_category,
        "confidence": round(confidence, 4),
        "model_status": "pretrained_zero_shot",
        "notice": (
            "This is a general-purpose AI prediction, not a verified "
            "identification. Check the item and local disposal guidance."
        )
    }


def classify_image(image_path):
    path = Path(image_path)

    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {path}")

    with Image.open(path) as image:
               return classify_image_content(image)

    best = results[0]
    matched_category = next(
        category
        for category, label in CANDIDATES.items()
        if label == best["label"]
    )

    confidence = float(best["score"])

    # These are demo thresholds, not scientifically validated limits.
    if confidence < 0.30:
        model_status = "low_confidence"
        notice = (
            "The model is uncertain about this result. "
            "Please verify the item manually before using the guidance."
        )
    elif matched_category == "other_e_waste":
        model_status = "other_e_waste"
        notice = (
            "The item may not match a specific supported category. "
            "Check the item and confirm its disposal guidance."
        )
    else:
        model_status = "pretrained_zero_shot"
        notice = (
            "General-purpose model prediction; "
            "not specifically validated for e-waste. "
            "Verify the category before disposal."
        )

    return {
        "category": matched_category,
        "confidence": round(confidence, 4),
        "model_status": model_status,
        "notice": notice,
    }

def classify_image_bytes(image_bytes):
    """Classify an image supplied as bytes."""
    from io import BytesIO
    from PIL import Image

    with Image.open(BytesIO(image_bytes)) as image:
                return classify_image_content(image)

    best = results[0]
    matched_category = next(
        category
        for category, label in CANDIDATES.items()
        if label == best["label"]
    )

    confidence = float(best["score"])

    # These are demo thresholds, not scientifically validated limits.
    if confidence < 0.30:
        model_status = "low_confidence"
        notice = (
            "The model is uncertain about this result. "
            "Please verify the item manually before using the guidance."
        )
    elif matched_category == "other_e_waste":
        model_status = "other_e_waste"
        notice = (
            "The item may not match a specific supported category. "
            "Check the item and confirm its disposal guidance."
        )
    else:
        model_status = "pretrained_zero_shot"
        notice = (
            "General-purpose model prediction; "
            "not specifically validated for e-waste. "
            "Verify the category before disposal."
        )

    return {
        "category": matched_category,
        "confidence": round(confidence, 4),
        "model_status": model_status,
        "notice": notice,
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