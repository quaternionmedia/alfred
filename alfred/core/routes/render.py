from fastapi import Depends
from typing import Optional
from .users import current_active_user, current_active_superuser
from ..models import UserRead as User
from ..models.render import Render, RenderUpdate
from otto.getdata import timestr
from ..utils.tasks import renderRemote
from ..utils.bucket import generate_signed_url
from fastapi_crudrouter import MotorCRUDRouter
from alfred.config import DB_URL, DB_NAME
from ..utils.db import get_client
from bson import ObjectId


class RenderAPI(MotorCRUDRouter):
    def __init__(
        self,
        schema=Render,
        create_schema=Render,
        update_schema=RenderUpdate,
        db_name=DB_NAME,
        *args,
        **kwargs,
    ):
        self.schema = schema
        self.create_schema = (create_schema,)
        self.update_schema = (update_schema,)
        self.db_name = db_name
        self.client = get_client()
        # self.db = self.client[DB_NAME]
        super().__init__(
            *args,
            **kwargs,
            schema=schema,
            client=self.client,
            create_schema=create_schema,
            update_schema=update_schema,
            db_url=DB_URL,
            database=DB_NAME,
        )

        @self.post('', *args, **kwargs)
        async def queueRender(
            render: Render, user: User = Depends(current_active_user)
        ):
            ts = timestr()
            filename = f'{render.project}{"_" + render.description if render.description else ""}_{render.width}x{render.height}{"_" + render.quality if render.quality else ""}_{render.edl.duration}s_{ts}.mp4'
            render.username = user.email
            render.filename = filename
            # TODO: rework to async logic
            result = await self.schema.insert_one(render)
            print('rendering!', render, result)
            renderRemote.delay(
                edl=render.edl,
                renderId=result.id,
                filename=filename,
                moviesize=(render.width, render.height),
                fps=render.fps,
                bitrate=render.bitrate,
                ffmpeg_params=render.ffmpeg_params,
            )
            return str(result.id)

        @self.post('/rerender/{id}', *args, **kwargs)
        async def reQueueRender(
            id: str, user: User = Depends(current_active_superuser)
        ):
            render = await self.schema.find_one({'_id': ObjectId(id)})
            print('rerendering!', id, render)
            renderRemote.delay(
                edl=render.edl,
                renderId=ObjectId(id),
                filename=render.filename,
                moviesize=(render.width, render.height),
                fps=render.fps,
                bitrate=render.bitrate,
                ffmpeg_params=render.ffmpeg_params,
            )

        @self.get('/{item_id}', *args, **kwargs)
        async def getSignedRenderLink(
            item_id: str, user: User = Depends(current_active_user)
        ):
            return generate_signed_url(item_id)

        @self.get('', *args, **kwargs)
        async def get_all_renders(skip: Optional[int] = 0, limit: Optional[int] = 100):
            return await self.schema.find_all().skip(skip).sort('-_id').to_list(limit)
