from datetime import timedelta
from os.path import join
from typing import Optional, Tuple
from urllib.parse import unquote, urlsplit

from bson import ObjectId
from google.cloud import storage

from alfred.config import BUCKET_NAME, DEFAULT_CHUNK_SIZE

from ..errors import Code, Refusal
from .db import get_sync_db

# Where signed URLs point; old stored links are signed URLs.
GCS_HOST = 'storage.googleapis.com'

# The canonical answers, for comparing against. Raise `fresh(...)` copies of
# them, not these instances themselves -- see `fresh`.
NOT_FOUND = Refusal(Code.NOT_FOUND, "Item not found")
INVALID_ID = Refusal(Code.INVALID_ID, "Not a valid identifier")


def fresh(exc: Refusal) -> Refusal:
    """A new refusal with `exc`'s code, status and detail, to raise in its place.

    Raising one shared instance over and over appends each raise's traceback
    to the one it already carries, so every 404 and 422 answered this way kept
    its request's frames -- and everything they referenced -- alive for the
    life of the process. A copy per raise leaves nothing behind.
    """
    return exc.again()


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


def signed_url(blob_name, minutes=15, bucket=None):
    """A v4 signed URL, valid for `minutes`, to download one object.

    By object name -- a render's `filename`, which is what `upload` names the
    object -- in `bucket`, or BUCKET_NAME. Needs a service account key file.
    """
    blob = get_bucket(bucket or BUCKET_NAME).blob(blob_name)
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=minutes),
        # Allow GET requests using this URL.
        method="GET",
    )


def object_reference(blob_name, bucket=None) -> str:
    """A lasting name for an object, `gs://<bucket>/<object>`: what a bucket
    delivery records, and signs only when somebody asks for the link."""
    return f'gs://{bucket or BUCKET_NAME}/{blob_name}'


def parse_reference(link) -> Optional[Tuple[str, str]]:
    """`(bucket, object)` for a stored bucket link, or None for anything else.

    A `gs://` reference; or a signed GCS URL, which is what a delivery stored
    before references -- long expired, but it still names the object.
    """
    if not isinstance(link, str):
        return None
    if link.startswith('gs://'):
        bucket, _, blob = link[len('gs://') :].partition('/')
    else:
        split = urlsplit(link)
        # V4 signs with `X-Goog-Signature`, V2 with `Signature`.
        signed = 'Signature=' in split.query
        if split.scheme != 'https' or split.hostname != GCS_HOST or not signed:
            return None
        bucket, _, blob = unquote(split.path).lstrip('/').partition('/')
    return (bucket, blob) if bucket and blob else None


def generate_signed_url(renderId, minutes=15):
    """A signed URL for a render's object in the bucket, by render id.

    Looks the render up to find its object name. Callers that already hold
    the render use `signed_url` with its filename instead.
    """
    db = get_sync_db()
    # bson's InvalidId is no pydantic error, so main.py's handler misses it:
    # the same 422 here (`/render/undefined` is a real request).
    if not ObjectId.is_valid(renderId):
        raise fresh(INVALID_ID)
    res = db.Render.find_one({'_id': ObjectId(renderId)})
    if not res:
        raise fresh(NOT_FOUND)
    return signed_url(res['filename'], minutes=minutes)
