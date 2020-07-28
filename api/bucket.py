from datetime import timedelta
from google.cloud import storage
from config import BUCKET_NAME
from os.path import join

def get_bucket(bucket=BUCKET_NAME):
    client = storage.Client()
    return client.bucket(bucket)

def upload(filename, directory=None):
    blob = get_bucket().blob(filename)
    blob.upload_from_filename(join(directory, filename) if directory else filename)

def generate_signed_url(filename):
    """Generates a v4 signed URL for downloading a blob.

    Note that this method requires a service account key file.
    """
    blob = get_bucket().blob(filename)

    return blob.generate_signed_url(
        version="v4",
        # This URL is valid for 15 minutes
        expiration=timedelta(minutes=15),
        # Allow GET requests using this URL.
        method="GET",
    )
