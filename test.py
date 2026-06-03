"""Manual smoke script for all public API endpoints.

Run after the stack is up:
    docker compose up --build -d
    python test.py

Optional environment variables:
    BASE_URL=http://localhost:8000
    TEST_EMAIL=test@example.com
    TEST_PASSWORD=TestPassword123!
    TEST_FULL_NAME="Test User"
    TEST_FILE_PATH=/path/to/file.pdf   # if omitted, a tiny PNG is generated
    TEST_DOCUMENT_ID=1                 # use an existing/processed document for results/export
    TEST_DELETE_DOCUMENT=1             # enable DELETE /api/documents/{id}
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import httpx

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
EMAIL = os.getenv("TEST_EMAIL", "test@example.com")
PASSWORD = os.getenv("TEST_PASSWORD", "TestPassword123!")
FULL_NAME = os.getenv("TEST_FULL_NAME", "Test User")
TEST_FILE_PATH = os.getenv("TEST_FILE_PATH")
TEST_DOCUMENT_ID = os.getenv("TEST_DOCUMENT_ID")
TEST_DELETE_DOCUMENT = os.getenv("TEST_DELETE_DOCUMENT", "0") == "1"
TIMEOUT = float(os.getenv("TEST_TIMEOUT", "30"))


class ApiSmoke:
    def __init__(self) -> None:
        self.client = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.api_key_id: int | None = None
        self.document_id: int | None = int(TEST_DOCUMENT_ID) if TEST_DOCUMENT_ID else None
        self._temp_file: str | None = None

    def close(self) -> None:
        if self._temp_file:
            Path(self._temp_file).unlink(missing_ok=True)
        self.client.close()

    @property
    def auth_headers(self) -> dict[str, str]:
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    def print_response(self, name: str, response: httpx.Response) -> None:
        print(f"\n{name}")
        print(f"{response.request.method} {response.request.url}")
        print(f"status={response.status_code}")
        body = response.text[:1200]
        if body:
            try:
                parsed: Any = response.json()
                body = json.dumps(parsed, ensure_ascii=False, indent=2)[:1200]
            except ValueError:
                pass
            print(body)

    def require_success(self, name: str, response: httpx.Response, allowed: tuple[int, ...] = (200,)) -> None:
        self.print_response(name, response)
        if response.status_code not in allowed:
            raise RuntimeError(f"{name} failed: expected {allowed}, got {response.status_code}")

    def health(self) -> None:
        response = self.client.get("/health")
        self.require_success("GET /health", response)

    def register(self) -> None:
        response = self.client.post(
            "/api/auth/register",
            json={"email": EMAIL, "password": PASSWORD, "full_name": FULL_NAME},
        )
        # 400 is OK when the user already exists from a previous smoke run.
        self.require_success("POST /api/auth/register", response, allowed=(201, 400))

    def login(self) -> None:
        response = self.client.post(
            "/api/auth/login",
            data={"username": EMAIL, "password": PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.require_success("POST /api/auth/login", response)
        payload = response.json()
        self.access_token = payload["access_token"]
        self.refresh_token = payload["refresh_token"]

    def refresh(self) -> None:
        response = self.client.post("/api/auth/refresh", json={"refresh_token": self.refresh_token})
        self.require_success("POST /api/auth/refresh", response)
        payload = response.json()
        self.access_token = payload["access_token"]
        self.refresh_token = payload["refresh_token"]

    def me(self) -> None:
        response = self.client.get("/api/auth/me", headers=self.auth_headers)
        self.require_success("GET /api/auth/me", response)

    def create_api_key(self) -> None:
        response = self.client.post(
            "/api/auth/api-keys",
            headers=self.auth_headers,
            json={
                "name": "Smoke test key",
                "expires_days": 1,
                "permissions": {"read": True, "write": True, "delete": True},
            },
        )
        self.require_success("POST /api/auth/api-keys", response, allowed=(201,))
        self.api_key_id = response.json()["id"]

    def list_api_keys(self) -> None:
        response = self.client.get("/api/auth/api-keys", headers=self.auth_headers)
        self.require_success("GET /api/auth/api-keys", response)

    def delete_api_key(self) -> None:
        if self.api_key_id is None:
            print("\nSKIP DELETE /api/auth/api-keys/{key_id}: no API key was created")
            return
        response = self.client.delete(f"/api/auth/api-keys/{self.api_key_id}", headers=self.auth_headers)
        self.require_success("DELETE /api/auth/api-keys/{key_id}", response, allowed=(204,))

    def _file_for_upload(self) -> tuple[str, bytes, str]:
        if TEST_FILE_PATH:
            path = Path(TEST_FILE_PATH)
            suffix = path.suffix.lower()
            content_type = {
                ".pdf": "application/pdf",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".tif": "image/tiff",
                ".tiff": "image/tiff",
            }.get(suffix, "application/octet-stream")
            return path.name, path.read_bytes(), content_type

        # 1x1 transparent PNG. It is enough to pass upload magic-byte validation.
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
        )
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp.write(png)
        tmp.close()
        self._temp_file = tmp.name
        return "smoke.png", png, "image/png"

    def upload_document(self) -> None:
        name, content, content_type = self._file_for_upload()
        response = self.client.post(
            "/api/documents/upload",
            headers=self.auth_headers,
            files={"file": (name, content, content_type)},
        )
        self.require_success("POST /api/documents/upload", response, allowed=(202,))
        self.document_id = response.json()["document_id"]

    def list_documents(self) -> None:
        response = self.client.get("/api/documents/", headers=self.auth_headers, params={"skip": 0, "limit": 20})
        self.require_success("GET /api/documents/", response)
        if self.document_id is None and response.json():
            self.document_id = response.json()[0]["id"]

    def document_status(self) -> None:
        if self.document_id is None:
            print("\nSKIP GET /api/documents/{doc_id}/status: no document id")
            return
        response = self.client.get(f"/api/documents/{self.document_id}/status", headers=self.auth_headers)
        self.require_success("GET /api/documents/{doc_id}/status", response)

    def document_results(self) -> None:
        if self.document_id is None:
            print("\nSKIP GET /api/documents/{doc_id}/results: no document id")
            return
        response = self.client.get(f"/api/documents/{self.document_id}/results", headers=self.auth_headers)
        # 400 is expected when the document is still queued/processing/error after upload.
        self.require_success("GET /api/documents/{doc_id}/results", response, allowed=(200, 400))

    def export_txt(self) -> None:
        self._export("GET /api/export/{doc_id}/txt", "txt")

    def export_json(self) -> None:
        self._export("GET /api/export/{doc_id}/json", "json")

    def export_csv(self) -> None:
        self._export("GET /api/export/{doc_id}/csv", "csv")

    def _export(self, title: str, fmt: str) -> None:
        if self.document_id is None:
            print(f"\nSKIP {title}: no document id")
            return
        response = self.client.get(f"/api/export/{self.document_id}/{fmt}", headers=self.auth_headers)
        # 400 is expected when the document is not processed yet.
        self.require_success(title, response, allowed=(200, 400))

    def search_text(self) -> None:
        response = self.client.get("/api/search/text", headers=self.auth_headers, params={"q": "тест", "limit": 10})
        self.require_success("GET /api/search/text", response)

    def search_semantic(self) -> None:
        response = self.client.get("/api/search/semantic", headers=self.auth_headers, params={"q": "тестовый документ", "limit": 10})
        # Semantic search can fail if pgvector/model assets are not ready; keep it visible as a smoke result.
        self.require_success("GET /api/search/semantic", response)

    def delete_document(self) -> None:
        if not TEST_DELETE_DOCUMENT:
            print("\nSKIP DELETE /api/documents/{doc_id}: set TEST_DELETE_DOCUMENT=1 to delete the document")
            return
        if self.document_id is None:
            print("\nSKIP DELETE /api/documents/{doc_id}: no document id")
            return
        response = self.client.delete(f"/api/documents/{self.document_id}", headers=self.auth_headers)
        self.require_success("DELETE /api/documents/{doc_id}", response, allowed=(204, 409))

    def logout(self) -> None:
        response = self.client.post("/api/auth/logout", headers=self.auth_headers)
        self.require_success("POST /api/auth/logout", response)

    def run_all(self) -> None:
        self.health()
        self.register()
        self.login()
        self.refresh()
        self.me()
        self.create_api_key()
        self.list_api_keys()
        self.upload_document()
        self.list_documents()
        self.document_status()
        self.document_results()
        self.export_txt()
        self.export_json()
        self.export_csv()
        self.search_text()
        self.search_semantic()
        self.delete_api_key()
        self.delete_document()
        self.logout()


if __name__ == "__main__":
    smoke = ApiSmoke()
    try:
        smoke.run_all()
    finally:
        smoke.close()
