import os
import mimetypes
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase environment variables are missing")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BUCKET_NAME = "aegispix-images"


def upload_file(local_path, storage_path):
    content_type, _ = mimetypes.guess_type(local_path)

    with open(local_path, "rb") as file:
        supabase.storage.from_(BUCKET_NAME).upload(
            path=storage_path,
            file=file,
            file_options={
                "content-type": content_type or "application/octet-stream",
                "upsert": "true"
            }
        )

    return storage_path


def download_file(storage_path, local_path):
    data = supabase.storage.from_(BUCKET_NAME).download(storage_path)

    with open(local_path, "wb") as file:
        file.write(data)

    return local_path


def delete_file(storage_path):
    supabase.storage.from_(BUCKET_NAME).remove([storage_path])
