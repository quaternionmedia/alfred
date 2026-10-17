from datetime import timedelta
from os.path import join

from bson import ObjectId
from fastapi import HTTPException
from google.cloud import storage

from alfred.config import BUCKET_NAME, DEFAULT_CHUNK_SIZE

from .db import get_sync_db

NOT_FOUND = HTTPException(status_code=404, detail="Item not found")
INVALID_ID = HTTPException(status_code=422, detail="Not a valid identifier")


def get_bucket(bucket=BUCKET_NAME):
    """Get bucket:
    Returns the storage bucket of the same name.
    Defaults to BUCKET_NAME from config (from environment variable)"""
    client = storage.Client()
    return client.bucket(bucket)


def upload(filename, directory=None):
    """Upload `directory/filename` as the object named `filename`."""
    blob = get_bucket().blob(filename, chunk_size=DEFAULT_CHUNK_SIZE)
    blob.upload_from_filename(join(directory, filename) if directory else filename)


def signed_url(blob_name, minutes=15):
    """A v4 signed URL, valid for `minutes`, to download one object.

    By object name -- a render's `filename`, which is what `upload` names the
    object. Needs a service account key file.
    """
    blob = get_bucket().blob(blob_name)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=minutes),
        # Allow GET requests using this URL.
        method="GET",
    )


def generate_signed_url(renderId, minutes=15):
    """A signed URL for a render's object in the bucket, by render id.

    Looks the render up to find its object name. Callers that already hold
    the render use `signed_url` with its filename instead.
    """
    db = get_sync_db()
    # `ObjectId(renderId)` raises bson's InvalidId on anything unparseable,
    # and nothing caught it, so `GET /render/undefined` answered 500 -- a
    # request the editor really does make, because its routes read a `project`
    # query parameter that is not always present. bson's error is not a
    # pydantic one, so the identifier handler in main.py does not see it;
    # this route needs its own guard, answering the same 422 that the project
    # routes now give for the same mistake.
    if not ObjectId.is_valid(renderId):
        raise INVALID_ID
    res = db.Render.find_one({'_id': ObjectId(renderId)})
    if not res:
        raise NOT_FOUND
    return signed_url(res['filename'], minutes=minutes)
