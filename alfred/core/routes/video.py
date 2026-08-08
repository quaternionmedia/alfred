from fastapi import APIRouter, Header
from os import listdir, makedirs
from os.path import join

from alfred.config import VIDEO_DIR
from ..responses import PartialFileResponse
from starlette.responses import Response

videoAPI = APIRouter()


@videoAPI.get('/videos')
async def getVideos():
    """# videos
    Get a list of all videos available locally on this instance"""
    # VIDEO_DIR rather than a bare 'videos' literal, and created if absent.
    # This listed a path relative to the working directory while the route
    # below hardcoded /app/videos -- two ways of naming one directory, in one
    # file, and `listdir` on a missing directory is a 500 rather than an empty
    # list, so a fresh install could not ask what media it had.
    makedirs(VIDEO_DIR, exist_ok=True)
    return [join('videos', f) for f in sorted(listdir(VIDEO_DIR))]


@videoAPI.get(
    '/videos/{video}',
    responses={
        206: {'content': {'video/mp4': {}}, 'description': 'partial video response'}
    },
)
async def buffer(video: str, response: Response, bits: int = Header(0)):
    """# video
    Get a specific video by filename.

    Returns an `HTTP 206 Partial Content` response,
    allowing the client to jump to a specific potion of a large video file.
    """
    return PartialFileResponse(join(VIDEO_DIR, video))
