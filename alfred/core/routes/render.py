from fastapi import Depends, HTTPException
from typing import Optional
from os.path import join
from .users import current_active_user, current_active_superuser
from ..models import UserRead as User
from ..models.render import Render, RenderUpdate
from otto.getdata import timestr
from ..utils.tasks import renderRemote
from ..utils.bucket import generate_signed_url, INVALID_ID, NOT_FOUND
from ..utils.destinations import DeliveryError, get_destination
from alfred.config import VIDEO_DIR
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
            render.username = user.email
            # TODO: rework to async logic
            result = await self.schema.insert_one(render)

            # The render's own id goes in the filename, because everything else
            # in it can repeat. It was project, description, size, quality,
            # duration and a second-resolution timestamp -- so two renders of
            # the same project in the same second produced the same filename
            # and the second silently overwrote the first's output. Three
            # concurrent renders in the e2e suite collided on exactly that and
            # ended up sharing one file, each reporting success.
            ts = timestr()
            filename = f'{render.project}{"_" + render.description if render.description else ""}_{render.width}x{render.height}{"_" + render.quality if render.quality else ""}_{render.edl.duration}s_{ts}_{result.id}.mp4'  # noqa: E501
            render.filename = filename
            await self.schema.find_one({'_id': result.id}).update(
                {'$set': {'filename': filename}}
            )
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

        @self.post('/{item_id}/deliver', *args, **kwargs)
        async def deliverRender(
            item_id: str,
            destination: Optional[str] = None,
            user: User = Depends(current_active_user),
        ):
            """# Deliver a render

            Sends a finished render to a destination and records where it went.

            The destination defaults to the project's saved one, then to
            `local` -- so a server with no cloud account still has somewhere to
            put a render, which the previous single path to a Google bucket did
            not allow.
            """
            if not ObjectId.is_valid(item_id):
                raise INVALID_ID
            render = await self.schema.find_one({'_id': ObjectId(item_id)})
            if render is None:
                raise NOT_FOUND
            if not render.filename:
                raise HTTPException(
                    status_code=409,
                    detail='That render has no output file yet',
                )

            chosen = destination or render.destination
            try:
                # VIDEO_DIR, not DATA_DIR. The Celery task writes finished
                # renders to videos/; this looked in data/ and would have
                # reported every render missing.
                delivery = get_destination(chosen).deliver(
                    join(VIDEO_DIR, render.filename)
                )
            except DeliveryError as exc:
                # 502, not 500: the render is fine and the request was valid.
                # Something downstream would not take it, and that is worth
                # retrying, which a 500 does not suggest.
                raise HTTPException(status_code=502, detail=str(exc)) from exc

            render.destination = delivery.destination
            render.link = delivery.location
            await render.save()
            return delivery

        @self.get('/{item_id}', *args, **kwargs)
        async def getSignedRenderLink(
            item_id: str, user: User = Depends(current_active_user)
        ):
            return generate_signed_url(item_id)

        @self.get('', *args, **kwargs)
        async def get_all_renders(skip: Optional[int] = 0, limit: Optional[int] = 100):
            return await self.schema.find_all().skip(skip).sort('-_id').to_list(limit)
