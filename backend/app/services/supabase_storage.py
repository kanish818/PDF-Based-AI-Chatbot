"""
Supabase Storage service for private PDF persistence.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class SupabaseStorageError(RuntimeError):
    pass


class SupabaseStorageService:
    def __init__(self) -> None:
        self.base_url = settings.SUPABASE_URL.rstrip("/")
        self.bucket = settings.SUPABASE_STORAGE_BUCKET
        self.timeout = httpx.Timeout(120.0, connect=15.0)

    def _headers(self, *, content_type: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def is_configured(self) -> bool:
        return bool(self.base_url and settings.SUPABASE_SERVICE_ROLE_KEY and self.bucket)

    def ensure_bucket(self) -> None:
        if not self.is_configured():
            raise SupabaseStorageError("Supabase storage is not configured.")

        with httpx.Client(timeout=self.timeout) as client:
            list_response = client.get(
                f"{self.base_url}/storage/v1/bucket",
                headers=self._headers(),
            )
            list_response.raise_for_status()
            buckets = list_response.json()
            if any(bucket.get("name") == self.bucket or bucket.get("id") == self.bucket for bucket in buckets):
                return

            create_response = client.post(
                f"{self.base_url}/storage/v1/bucket",
                headers=self._headers(content_type="application/json"),
                json={"id": self.bucket, "name": self.bucket, "public": False},
            )
            if create_response.status_code not in (200, 201, 409):
                raise SupabaseStorageError(
                    f"Could not create Supabase bucket '{self.bucket}': {create_response.text}"
                )
            logger.info("Supabase bucket '%s' created.", self.bucket)

    def upload_bytes(self, object_key: str, content: bytes, content_type: str = "application/pdf") -> None:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/storage/v1/object/{self.bucket}/{object_key}",
                headers={**self._headers(content_type=content_type), "x-upsert": "false"},
                content=content,
            )
            if response.status_code not in (200, 201):
                raise SupabaseStorageError(f"Supabase upload failed: {response.text}")

    def download_to_tempfile(self, object_key: str) -> str:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(
                f"{self.base_url}/storage/v1/object/{self.bucket}/{object_key}",
                headers=self._headers(),
            )
            if response.status_code != 200:
                raise SupabaseStorageError(f"Supabase download failed: {response.text}")

        suffix = Path(object_key).suffix or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(response.content)
            return tmp.name

    def delete_object(self, object_key: str) -> None:
        with httpx.Client(timeout=self.timeout) as client:
            response = client.delete(
                f"{self.base_url}/storage/v1/object/{self.bucket}/{object_key}",
                headers=self._headers(),
            )
            if response.status_code not in (200, 204, 404):
                raise SupabaseStorageError(f"Supabase delete failed: {response.text}")


storage_service = SupabaseStorageService()
