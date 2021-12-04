from fastapi import HTTPException
from datetime import timedelta
from google.cloud import storage
from alfred.config import BUCKET_NAME, DEFAULT_CHUNK_SIZE
from os.path import join
from .db import get_sync_db
from bson import ObjectId

NOT_FOUND = HTTPException(status_code=404, detail="Item not found")

def get_bucket(bucket=BUCKET_NAME):
    """Get bucket:
    Returns the storage bucket of the same name.
    Defaults to BUCKET_NAME from config (from environment variable)"""
    client = storage.Client()
    return client.bucket(bucket)

def upload(filename, directory=None):
    """Upload file to cloud directory"""
    blob = get_bucket().blob(filename, chunk_size=DEFAULT_CHUNK_SIZE)
    blob.upload_from_filename(join(directory, filename) if directory else filename)

def generate_signed_url(renderId, minutes=15):
    """Generates a v4 signed URL for downloading a blob.

    Note that this method requires a service account key file.
    """
    db = get_sync_db()
    res = db.Render.find_one({'_id': ObjectId(renderId)})
    if not res:
        raise NOT_FOUND
    print('generating url', res)
    blob = get_bucket().blob(res['filename'])
    return blob.generate_signed_url(
        version="v4",
        # This URL is valid for 15 minutes
        expiration=timedelta(minutes=minutes),
        # Allow GET requests using this URL.
        method="GET",
    )
