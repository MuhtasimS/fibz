from __future__ import annotations
from typing import List, Tuple, Dict
from pypdf import PdfReader
import pathlib, hashlib

def fingerprint(path: str) -> str:
    p = pathlib.Path(path)
    h = hashlib.sha1()
    with open(p, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()[:16]

def chunk_text(text: str, max_chars: int = 3000) -> List[str]:
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i+max_chars])
        i += max_chars
    return chunks

def extract_pdf(path: str) -> List[Dict]:
    p = pathlib.Path(path)
    fp = fingerprint(str(p))
    reader = PdfReader(str(p))
    records: List[Dict] = []
    for page_num, page in enumerate(reader.pages, start=1):
        t = page.extract_text() or ""
        for ch in chunk_text(t):
            records.append({
                "id": f"pdf:{fp}:p{page_num}:{hash(ch)%10_000_000}",
                "text": ch,
                "meta": {"modality":"file","filetype":"pdf","filename":p.name,"page":page_num,"fingerprint":fp},
            })
    return records
