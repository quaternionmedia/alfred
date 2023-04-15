from fastapi import APIRouter, Header
from os import listdir
from os.path import join
from ..responses import PartialFileResponse
from starlette.responses import Response

videoAPI = APIRouter()


@videoAPI.get('/videos')
async def getVideos():
    """# videos
    Get a list of all videos available locally on this instance"""
    return [join('videos', f) for f in listdir('videos')]


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
    return PartialFileResponse(join('/app/videos', video))
