from __future__ import annotations
from typing import List, Tuple
from PIL import Image, ExifTags
import pathlib
from fibz_bot.config import settings

try:
    from google.cloud import vision
except Exception:
    vision = None

def extract_exif(path: str) -> dict:
    meta = {}
    try:
        img = Image.open(path)
        exif_data = img.getexif()
        if exif_data:
            for tag_id, value in exif_data.items():
                tag = ExifTags.TAGS.get(tag_id, tag_id)
                meta[str(tag)] = str(value)
    except Exception:
        pass
    return meta

def ocr_text(path: str) -> str:
    if not settings.ENABLE_VISION_OCR or vision is None:
        return ""
    try:
        client = vision.ImageAnnotatorClient()
        with open(path, "rb") as f:
            content = f.read()
        image = vision.Image(content=content)
        response = client.text_detection(image=image)
        if response and response.text_annotations:
            return response.text_annotations[0].description or ""
    except Exception:
        return ""
    return ""

def parse_image(path: str) -> List[Tuple[str, dict]]:
    p = pathlib.Path(path)
    meta = {"modality":"image","filename":p.name}
    meta.update(extract_exif(path))
    text = ocr_text(path)
    desc = f"Image {p.name}."
    if text:
        desc += f" OCR text: {text[:2000]}"
    return [(desc, meta)]
