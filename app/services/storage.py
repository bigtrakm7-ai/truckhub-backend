"""S3-compatible storage service for file uploads.

Supports: product images, documents, price uploads, service photos.
Falls back to local filesystem when S3 is not configured.
"""

import os
import uuid
from typing import Optional, BinaryIO
from datetime import datetime
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "pdf", "xls", "xlsx", "csv", "xml", "yml"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


class StorageService:
    """Unified storage interface: S3 when configured, local filesystem fallback."""

    def __init__(self):
        self.s3_bucket = getattr(settings, "S3_BUCKET", "")
        self.s3_endpoint = getattr(settings, "S3_ENDPOINT", "")
        self.s3_access_key = getattr(settings, "S3_ACCESS_KEY", "")
        self.s3_secret_key = getattr(settings, "S3_SECRET_KEY", "")
        self._s3_client = None

    @property
    def is_s3_configured(self) -> bool:
        return bool(self.s3_bucket and self.s3_access_key and self.s3_secret_key)

    def _get_s3_client(self):
        if self._s3_client is None and self.is_s3_configured:
            try:
                import boto3
                self._s3_client = boto3.client(
                    "s3",
                    endpoint_url=self.s3_endpoint or None,
                    aws_access_key_id=self.s3_access_key,
                    aws_secret_access_key=self.s3_secret_key,
                    region_name=getattr(settings, "S3_REGION", "ru-1"),
                )
            except ImportError:
                logger.warning("boto3_not_installed")
        return self._s3_client

    def upload(self, file_data: BinaryIO, filename: str, folder: str = "general") -> str:
        """Upload a file. Returns URL/path to the stored file."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"File type .{ext} not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

        unique_name = f"{folder}/{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex[:8]}.{ext}"

        if self.is_s3_configured:
            return self._upload_s3(file_data, unique_name, ext)
        return self._upload_local(file_data, unique_name)

    def _upload_s3(self, file_data: BinaryIO, key: str, ext: str) -> str:
        client = self._get_s3_client()
        content_type = self._content_type(ext)
        try:
            client.upload_fileobj(
                file_data,
                self.s3_bucket,
                key,
                ExtraArgs={"ContentType": content_type},
            )
            url = f"{self.s3_endpoint}/{self.s3_bucket}/{key}" if self.s3_endpoint else f"https://{self.s3_bucket}.s3.amazonaws.com/{key}"
            logger.info("s3_upload_success", extra={"extra": {"key": key}})
            return url
        except Exception as exc:
            logger.warning("s3_upload_failed", extra={"extra": {"error": str(exc)}})
            return self._upload_local(file_data, key)

    def _upload_local(self, file_data: BinaryIO, relative_path: str) -> str:
        full_path = os.path.join(UPLOAD_DIR, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "wb") as f:
            f.write(file_data.read())
        logger.info("local_upload_success", extra={"extra": {"path": relative_path}})
        return f"/uploads/{relative_path}"

    def delete(self, file_url: str) -> bool:
        """Delete a stored file."""
        if self.is_s3_configured and not file_url.startswith("/uploads/"):
            try:
                key = file_url.split(f"/{self.s3_bucket}/")[-1]
                self._get_s3_client().delete_object(Bucket=self.s3_bucket, Key=key)
                return True
            except Exception:
                return False
        else:
            local_path = os.path.join(UPLOAD_DIR, file_url.replace("/uploads/", ""))
            if os.path.exists(local_path):
                os.remove(local_path)
                return True
        return False

    @staticmethod
    def _content_type(ext: str) -> str:
        types = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp", "pdf": "application/pdf",
            "xls": "application/vnd.ms-excel", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "csv": "text/csv", "xml": "application/xml", "yml": "application/xml",
        }
        return types.get(ext, "application/octet-stream")


# Singleton
storage = StorageService()
