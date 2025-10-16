from __future__ import annotations
from typing import Optional
import os, time
from google.cloud import storage

def get_client() -> storage.Client:
    return storage.Client()

def upload_file(local_path: str, bucket_name: str, dest_path: str, make_public: bool = False) -> str:
    client = get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(dest_path)
    blob.upload_from_filename(local_path)
    if make_public:
        blob.make_public()
        return blob.public_url
    return f"gs://{bucket_name}/{dest_path}"

def upload_bytes(data: bytes, bucket_name: str, dest_path: str, content_type: str | None = None, make_public: bool = False) -> str:
    client = get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(dest_path)
    blob.upload_from_string(data, content_type=content_type)
    if make_public:
        blob.make_public()
        return blob.public_url
    return f"gs://{bucket_name}/{dest_path}"
