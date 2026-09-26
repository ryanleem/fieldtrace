from types import SimpleNamespace
from uuid import uuid4

import pymupdf
import pytest

from app.services.pdf_parser import parse_pdf
from app.services.chunking import chunk_pages


class OCR:
    def __init__(self):
        self.calls = 0

    def extract(self, image):
        self.calls += 1
        w, h = image.size
        return SimpleNamespace(raw_text='TEST 5091', provider='test-fixture', warnings=[],
            lines=[{'text': 'TEST 5091', 'bbox': [[0, 0], [w, 0], [w, h], [0, h]]}])


def document(tmp_path, text=None):
    path = tmp_path / 'fixture.pdf'
    with pymupdf.open() as doc:
        page = doc.new_page(width=300, height=400)
        if text:
            page.insert_text((70, 100), text)
        doc.save(path)
    return path


def test_default_does_not_invoke_ocr(tmp_path):
    provider = OCR()
    pages = parse_pdf(document(tmp_path), uuid4(), ocr_provider=provider)
    assert provider.calls == 0
    assert not pages[0].text


def test_text_page_never_uses_ocr(tmp_path):
    provider = OCR()
    pages = parse_pdf(document(tmp_path, 'Existing source text'), uuid4(),
                      ocr_enabled=True, ocr_provider=provider)
    assert provider.calls == 0
    assert 'Existing source text' in pages[0].text


def test_ocr_provenance_coordinates_and_warning_reach_chunks(tmp_path):
    provider = OCR()
    pages = parse_pdf(document(tmp_path), uuid4(), ocr_enabled=True, ocr_provider=provider)
    assert provider.calls == 1
    assert pages[0].extraction_method == 'ocr:test-fixture'
    assert pages[0].units[0].bbox == pytest.approx([0, 0, 300, 400])
    chunks = chunk_pages(pages)
    assert chunks[0].page_number == 1
    assert chunks[0].content_type == 'ocr_text'
    assert any('OCR transcription' in note for note in chunks[0].extraction_notes)


def test_ocr_failure_is_not_silently_treated_as_blank(tmp_path):
    class Broken:
        def extract(self, image):
            raise ValueError('fixture failure')
    with pytest.raises(RuntimeError, match='Document OCR failed on page 1'):
        parse_pdf(document(tmp_path), uuid4(), ocr_enabled=True, ocr_provider=Broken())


def test_native_parser_runtime_error_preserves_pypdf_fallback(tmp_path, monkeypatch):
    path = document(tmp_path, 'Original manual evidence')
    def broken(*args, **kwargs):
        raise RuntimeError('native parser fixture failure')
    monkeypatch.setattr(pymupdf.Page, 'get_text', broken)
    page = parse_pdf(path, uuid4())[0]
    assert page.extraction_method == 'pypdf_fallback'
    assert 'Original manual evidence' in page.text
    assert page.units[0].text == page.text


@pytest.mark.parametrize('rotation,display_box', [
    (0, [20, 30, 80, 90]), (90, [310, 20, 370, 80]),
    (180, [220, 310, 280, 370]), (270, [30, 220, 90, 280]),
])
@pytest.mark.parametrize('cropped', [False, True])
def test_rotated_cropped_scan_boxes_match_native_coordinates(tmp_path, rotation, display_box, cropped):
    path = tmp_path / 'rotated.pdf'
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=340 if cropped else 300, height=460 if cropped else 400)
        if cropped:
            page.set_cropbox(pymupdf.Rect(10, 20, 310, 420))
        page.set_rotation(rotation)
        pdf.save(path)

    class PositionedOCR:
        def extract(self, image):
            # Fixtures specify the location in the rendered (rotated) page, in points.
            width, height = (400, 300) if rotation in (90, 270) else (300, 400)
            x0, y0, x1, y1 = display_box
            points = [[x * image.width / width, y * image.height / height]
                      for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]]
            return SimpleNamespace(raw_text='5091', provider='fixture', warnings=[],
                                   lines=[{'text': '5091', 'bbox': points}])

    page = parse_pdf(path, uuid4(), ocr_enabled=True, ocr_provider=PositionedOCR())[0]
    assert page.units[0].bbox == pytest.approx([20, 30, 80, 90])


def test_lazy_provider_reused_only_for_textless_pages(tmp_path, monkeypatch):
    path = tmp_path / 'mixed.pdf'
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((70, 100), 'Original native text')
        pdf.new_page()
        pdf.new_page()
        pdf.save(path)
    provider = OCR()
    loads = []
    def factory():
        loads.append(True)
        return provider
    monkeypatch.setattr('app.services.equipment_ocr.get_ocr_provider', factory)
    pages = parse_pdf(path, uuid4(), ocr_enabled=True)
    assert loads == [True] and provider.calls == 2
    assert pages[0].extraction_method == 'pymupdf'
    assert [p.page_number for p in pages] == [1, 2, 3]
    assert all(p.extraction_method.startswith('ocr:') for p in pages[1:])


def test_ocr_raster_is_bounded_and_blank_output_remains_blank(tmp_path):
    path = tmp_path / 'large.pdf'
    with pymupdf.open() as pdf:
        pdf.new_page(width=3000, height=4000)
        pdf.save(path)
    class BlankOCR:
        def extract(self, image):
            assert image.mode == 'RGB' and max(image.size) <= 2400
            return SimpleNamespace(raw_text='', provider='fixture', warnings=[], lines=[])
    page = parse_pdf(path, uuid4(), ocr_enabled=True, ocr_provider=BlankOCR())[0]
    assert page.text == '' and page.units == []
    assert any('OCR found no text' in note for note in page.warnings)
    assert chunk_pages([page]) == []


def test_ocr_setting_defaults_off_and_can_be_enabled(monkeypatch):
    from app.config import Settings
    monkeypatch.delenv('DOCUMENT_OCR_ENABLED', raising=False)
    assert Settings(_env_file=None).document_ocr_enabled is False
    monkeypatch.setenv('DOCUMENT_OCR_ENABLED', 'true')
    assert Settings(_env_file=None).document_ocr_enabled is True


def test_ingest_api_explains_ocr_failure_without_provider_details(monkeypatch):
    from app.api import documents
    from app.schemas.document import IngestRequest
    from app.services.pdf_parser import DocumentOCRError
    from fastapi import HTTPException
    monkeypatch.setattr(documents, 'get_engine', lambda: None)
    monkeypatch.setattr(documents, 'get_embedder', lambda: None)
    def fail(*args):
        raise DocumentOCRError('Document OCR failed on page 2')
    monkeypatch.setattr(documents, 'ingest', fail)
    with pytest.raises(HTTPException) as error:
        documents.ingest_document(IngestRequest(filename='scan.pdf', title='Scan fixture'))
    assert error.value.status_code == 503
    assert error.value.detail == {'errors': ['Document OCR failed on page 2']}


@pytest.mark.integration
def test_scanned_ingestion_provenance_and_failed_replacement_roll_back(isolated_db, monkeypatch):
    from sqlalchemy import select, func
    from sqlalchemy.orm import Session
    from app.models import Document, DocumentPage, DocumentChunk
    from app.schemas.document import IngestRequest
    from app.services.ingestion import ingest
    from app.services.pdf_parser import DocumentOCRError
    engine, settings, embedder = isolated_db
    # A real image-only PDF: no embedded text layer for the native parser to extract.
    path = settings.manuals_dir / 'scan.pdf'
    with pymupdf.open() as source, pymupdf.open() as scan:
        page = source.new_page(width=300, height=400)
        page.insert_text((40, 100), 'ABB ACS880 fault 5091', fontsize=16)
        scan.new_page(width=300, height=400).insert_image(page.rect, stream=page.get_pixmap().tobytes('png'))
        scan.save(path)
    request = IngestRequest(filename='scan.pdf', title='Synthetic scanned fixture', equipment_model='ACS880')
    settings.document_ocr_enabled = False
    with pytest.raises(ValueError, match='no extractable text'):
        ingest(engine, request, embedder, settings)
    settings.document_ocr_enabled = True
    monkeypatch.setattr('app.services.equipment_ocr.get_ocr_provider', lambda: OCR())
    result = ingest(engine, request, embedder, settings)
    assert result.chunks_created > 0
    with Session(engine) as db:
        page = db.scalar(select(DocumentPage).where(DocumentPage.document_id == result.document_id))
        chunk = db.scalar(select(DocumentChunk).where(DocumentChunk.document_id == result.document_id))
        assert page.extraction_method == 'ocr:test-fixture' and page.page_number == 1
        assert chunk.content_type == 'ocr_text' and chunk.source_blocks[0]['bbox']
        assert any('OCR transcription' in note for note in chunk.extraction_notes)
    def unavailable():
        raise ValueError('internal model fixture unavailable')
    monkeypatch.setattr('app.services.equipment_ocr.get_ocr_provider', unavailable)
    assert ingest(engine, request, embedder, settings).duplicate is True
    with pytest.raises(DocumentOCRError, match='page 1'):
        ingest(engine, request, embedder, settings, replace=True)
    with Session(engine) as db:
        assert db.get(Document, result.document_id).chunks_created == result.chunks_created
        assert db.scalar(select(func.count()).select_from(DocumentChunk)) == result.chunks_created
        assert db.scalar(select(DocumentPage.extracted_text)) == 'TEST 5091'
