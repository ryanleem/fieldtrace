"""Swappable local OCR provider. No appearance classification or external APIs."""
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from io import BytesIO
from threading import Lock
from typing import Protocol
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000


@dataclass
class OCRResult:
    raw_text: str
    provider: str
    lines: list = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class OCRProvider(Protocol):
    def extract(self, image: Image.Image) -> OCRResult: ...


def decode_image(data):
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image must contain 1 byte to 10 MiB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                if source.format not in {'JPEG', 'PNG', 'WEBP'}:
                    raise ValueError("Supported image formats: JPEG, PNG, WEBP")
                if source.width * source.height > MAX_IMAGE_PIXELS:
                    raise ValueError("Image exceeds 16 million pixels")
                if getattr(source, 'n_frames', 1) != 1:
                    raise ValueError("Upload a single still image")
                image = ImageOps.exif_transpose(source).convert('RGB')
                image.thumbnail((2200, 2200))
                return image.copy()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError("Image could not be decoded safely") from error


class RapidOCRProvider:
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        self.engine = RapidOCR()
        self.lock = Lock()

    def extract(self, image):
        import numpy as np
        with self.lock:
            result, _ = self.engine(np.asarray(image)[:, :, ::-1].copy())
        lines = [{'text': item[1], 'recognition_score': float(item[2]),
                  'bbox': [[float(x), float(y)] for x, y in item[0]]} for item in result or []]
        return OCRResult(raw_text='\n'.join(line['text'] for line in lines), provider='rapidocr-onnxruntime/1.4.4',
                         lines=lines, warnings=[] if lines else ['No readable text detected; provide a clearer nameplate.'])


@lru_cache
def get_ocr_provider() -> OCRProvider:
    return RapidOCRProvider()
