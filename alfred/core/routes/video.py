from os import makedirs

from fastapi import APIRouter, Depends, HTTPException

from alfred.config import VIDEO_DIR

from ..responses import PartialFileResponse
from ..utils.media import LIBRARY_PREFIX, library_file, library_files, media_type
from .media import MediaAccess, media_access

# The listing, mounted behind the session like every other route.
videoAPI = APIRouter()

# Not behind the session: a `<video>` or `<img>` fetches by signed URL (M1).
videoFileAPI = APIRouter()


# A plain function, so listing the library runs in the thread pool.
@videoAPI.get('/videos')
def getVideos():
    """# videos
    Get a list of all videos available locally on this instance.

    Each entry is a media name a clip can use as it is: `videos/<file>`.
    `GET /media` lists the same files with what is known about each.
    """
    # Created if absent, so a fresh install lists nothing rather than a 500.
    # Only names a render accepts back: one rule for both.
    makedirs(VIDEO_DIR, exist_ok=True)
    return [LIBRARY_PREFIX + name for name in library_files(VIDEO_DIR)]


@videoFileAPI.get(
    '/videos/{video}',
    responses={
        206: {'content': {'video/mp4': {}}, 'description': 'the requested range'},
        401: {'description': 'no session, and no valid signature for this path'},
        404: {'description': 'no such file in the media library'},
    },
)
async def buffer(video: str, access: MediaAccess = Depends(media_access)):
    """# video
    Get a specific video by filename.

    The whole file when there is no `Range` header, and `206 Partial Content`
    for the requested range when there is one, so a player can seek.

    With a session, or with no session through the signed `url` that `GET
    /media` lists for the file -- which a `<video>` or `<img>` can use as its
    `src`, and stream from.
    """
    # Contained in the library and existing, or 404.
    path = library_file(video, VIDEO_DIR)
    if path is None:
        raise HTTPException(status_code=404, detail='No such file in the media library')
    # Typed by extension: an unknown one guessed as text/plain will not play.
    return PartialFileResponse(path, media_type=media_type(video))
