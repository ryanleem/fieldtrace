"""Repeatable source checks; raw text and representative rendered pages for QA."""
import hashlib
import json
from pathlib import Path
import re
import sys
from uuid import NAMESPACE_URL, uuid5

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.pdf_parser import parse_pdf


def main():
    target = ROOT / "work/pdf-inspection"
    target.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "data/manuals/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for item in manifest:
        path = ROOT / "data/manuals" / item["filename"]
        pdf = pymupdf.open(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        is_drive = "acs880" in path.name
        number, revision, page = ("3AUA0000085967", "V", 3) if is_drive else ("3BFP 000 050 R0101", "L", 132)
        text = pdf[page-1].get_text()
        assert number in text and re.search(r"REV\s+" + revision + r"\b", text, re.I)
        assert "ABB" in text
        item.update(document_number=number, revision=revision, verified_sha256=digest,
                    metadata_verification={"physical_pdf_pages": [1, page],
                                           "method": "Title/colophon text checked against PDF; representative pages rendered for visual review",
                                           "bibliographic_text": f"{number} Rev {revision}",
                                           "equipment_model_note": "Family-level manual; no single model" if not is_drive else "ACS880 stated on cover"})
        doc_id = uuid5(NAMESPACE_URL, "abb-guardian:sha256:" + digest)
        pages = parse_pdf(path, doc_id)
        (target / (path.stem + ".json")).write_text(json.dumps([
            {"page": p.page_number, "text": p.text, "warnings": p.warnings,
             "units": [{"text": u.text, "section": u.section_title, "kind": u.content_type,
                        "heading": u.heading, "bbox": u.bbox} for u in p.units]} for p in pages
        ], ensure_ascii=False, indent=2), encoding="utf-8")
        matches = []
        for p in pages:
            if re.search(r"overheat|overtemperature|fault tracing|high temperature", p.text, re.I):
                matches.append(p.page_number)
        print(path.name, "pages", len(pages), "matching pages", matches)
        # Inspect tables where relevant source text occurs, plus publication metadata.
        chosen = [page]
        if is_drive:
            chosen += [p.page_number for p in pages if "Motor overtemperature" in p.text][:2]
        else:
            chosen += [p.page_number for p in pages if "Overheating" in p.text or "High temperature" in p.text][:3]
        for physical in chosen:
            pdf[physical-1].get_pixmap(matrix=pymupdf.Matrix(1.2, 1.2)).save(target / f"{path.stem}-p{physical}.png")
        print("Rendered", chosen)
        print("Confirmed metadata", number, revision)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
