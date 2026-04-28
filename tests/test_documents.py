import io
import pytest


def _fake_pdf() -> bytes:
    """Минимальный валидный PDF."""
    return b"%PDF-1.4 1 0 obj<</Type /Catalog>>endobj\n%%EOF"


def _fake_jpg() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 100


@pytest.mark.asyncio
async def test_upload_pdf(client, auth_headers):
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("test.pdf", io.BytesIO(_fake_pdf()), "application/pdf")},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert "document_id" in data
    assert data["status"] == "uploaded"
    assert data["celery_task_id"] is not None


@pytest.mark.asyncio
async def test_upload_invalid_type(client, auth_headers):
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("virus.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_requires_auth(client):
    resp = await client.post(
        "/api/documents/upload",
        files={"file": ("test.pdf", io.BytesIO(_fake_pdf()), "application/pdf")},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_documents(client, auth_headers):
    # Загружаем документ
    await client.post(
        "/api/documents/upload",
        files={"file": ("test.pdf", io.BytesIO(_fake_pdf()), "application/pdf")},
        headers=auth_headers,
    )
    resp = await client.get("/api/documents/", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_document_status(client, auth_headers):
    upload = await client.post(
        "/api/documents/upload",
        files={"file": ("test.pdf", io.BytesIO(_fake_pdf()), "application/pdf")},
        headers=auth_headers,
    )
    doc_id = upload.json()["document_id"]

    resp = await client.get(f"/api/documents/{doc_id}/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["document_id"] == doc_id


@pytest.mark.asyncio
async def test_document_not_found(client, auth_headers):
    resp = await client.get("/api/documents/999999/status", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_results_not_ready(client, auth_headers):
    """Документ только загружен — результаты ещё недоступны."""
    upload = await client.post(
        "/api/documents/upload",
        files={"file": ("test.pdf", io.BytesIO(_fake_pdf()), "application/pdf")},
        headers=auth_headers,
    )
    doc_id = upload.json()["document_id"]
    resp = await client.get(f"/api/documents/{doc_id}/results", headers=auth_headers)
    # Статус не PROCESSED — должна быть ошибка 400
    assert resp.status_code == 400
