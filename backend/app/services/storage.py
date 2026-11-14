"""Recording storage: Cloudflare R2 (S3-compatible) in production, local folder in development."""

from __future__ import annotations

from pathlib import Path

from flask import current_app


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("invalid storage key")
        return p

    def put(self, key: str, data: bytes, content_type: str = "audio/wav") -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class R2Storage:
    def __init__(self, account_id: str, access_key: str, secret_key: str, bucket: str):
        import boto3  # imported lazily so dev/test does not need credentials

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )

    def put(self, key: str, data: bytes, content_type: str = "audio/wav") -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def get_storage():
    app = current_app
    cached = app.extensions.get("qi_storage")
    if cached is not None:
        return cached
    cfg = app.config
    if cfg["STORAGE_BACKEND"] == "r2":
        storage = R2Storage(
            cfg["R2_ACCOUNT_ID"],
            cfg["R2_ACCESS_KEY_ID"],
            cfg["R2_SECRET_ACCESS_KEY"],
            cfg["R2_BUCKET"],
        )
    else:
        storage = LocalStorage(cfg["LOCAL_STORAGE_DIR"])
    app.extensions["qi_storage"] = storage
    return storage
