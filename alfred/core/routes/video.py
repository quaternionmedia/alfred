from os import makedirs

from fastapi import APIRouter, Depends, HTTPException

from alfred.config import VIDEO_DIR

from ..responses import PartialFileResponse
from ..utils.media import LIBRARY_PREFIX, library_file, library_files, media_type
from .media import MediaAccess, media_access

# The listing, mounted behind the session like every other route.
videoAPI = APIRouter()

# The files, on a router of their own: a browser fetches them by itself from a
# `<video>` or `<img>`, with a signed URL rather than a session (contract M1;
# `GET /media` hands the URLs out).
videoFileAPI = APIRouter()


# A plain function, not a coroutine: FastAPI runs it in its thread pool.
# Listing the library looks up every entry in it, and as a coroutine that ran
# on the event loop: on a Docker Desktop bind mount a library of 120 files
# took a fifth of a second, in which the api answered nothing else. `GET
# /media` lists the same files, and more slowly, in the thread pool too.
@videoAPI.get('/videos')
def getVideos():
    """# videos
    Get a list of all videos available locally on this instance.

    Each entry is a media name a clip can use as it is: `videos/<file>`.
    `GET /media` lists the same files with what is known about each.
    """
    # VIDEO_DIR rather than a bare 'videos' literal, and created if absent.
    # This listed a path relative to the working directory while the route
    # below hardcoded /app/videos -- two ways of naming one directory, in one
    # file, and `listdir` on a missing directory is a 500 rather than an empty
    # list, so a fresh install could not ask what media it had.
    #
    # Files only, and only names a render accepts back. This listed every
    # directory entry, so a subdirectory showed up as media no clip could use.
    # What is listed here and what POST /render accepts are now one rule.
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
    # Contained and existing, or 404. A name that did not exist was a 500, and
    # the path parameter was joined onto the media directory with no
    # containment check -- safe only because `{video}` cannot match a `/`.
    path = library_file(video, VIDEO_DIR)
    if path is None:
        raise HTTPException(status_code=404, detail='No such file in the media library')
    # Typed by its extension. Left to guess, an extension Python does not know
    # was served as text/plain, which no browser will play.
    return PartialFileResponse(path, media_type=media_type(video))
