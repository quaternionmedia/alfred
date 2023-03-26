from fastapi import FastAPI, Depends
from fastapi.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles
from beanie import init_beanie

from subprocess import run as bash

from alfred.core.routes import authAPI
from alfred.core.routes import videoAPI
from alfred.core.routes import issueAPI
from alfred.core.routes import adminAPI
from alfred.core.routes import fontAPI
from alfred.core.routes import ProjectAPI
from alfred.core.routes import RenderAPI
from alfred.core.routes import previewAPI

# from otto.main import app as ottoApi
from alfred.core.utils import get_db

# from alfred.core.utils.db import deOid
from alfred.core.routes.users import (
    fastapi_users,
    current_active_user,
    current_active_superuser,
)
from alfred.core.models.users import UserRead, UserUpdate
from alfred.core.utils.db import User
from alfred import docs


app = FastAPI(
    title=docs.title,
    description=docs.description,
    version=docs.version,
    contact=docs.contact,
    openapi_tags=docs.tags_metadata,
    docs_url='/api',
)
app.add_middleware(GZipMiddleware)


@app.on_event('startup')
async def seedDb():
    db = get_db()
    if not db.Project.count_documents({}):
        from seed import seed

        await db.Project.insert_many(seed)


@app.on_event('startup')
async def checkFonts():
    db = get_db()
    fonts = (
        bash(['fc-list', '-f', '"%{family}-%{style}\n"'], capture_output=True)
        .stdout.decode()
        .replace('"', '')
        .split('\n')
    )
    for f in fonts:
        if f:
            font = f.split('-')
            for fam in font[0].split(','):
                await db.fonts.update_one(
                    {'family': fam.replace(' ', '-')},
                    {
                        '$set': {
                            'style': [i.replace(' ', '-') for i in font[1].split(',')]
                        }
                    },
                    upsert=True,
                )
    # db.fonts.update_many(results, upsert=True)


app.include_router(authAPI, prefix='/auth', tags=['auth'])
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix='/users',
    tags=['users'],
)

renders = RenderAPI()
app.include_router(
    renders, dependencies=[Depends(current_active_user)], tags=['render']
)

projects = ProjectAPI()
app.include_router(
    projects, dependencies=[Depends(current_active_user)], tags=['project']
)

app.include_router(fontAPI, dependencies=[Depends(current_active_user)], tags=['font'])
app.include_router(
    videoAPI, dependencies=[Depends(current_active_user)], tags=['video']
)
app.include_router(
    previewAPI,
    prefix='/preview',
    dependencies=[Depends(current_active_user)],
    tags=['preview'],
)
app.include_router(
    issueAPI,
    prefix='/render',
    dependencies=[Depends(current_active_user)],
    tags=['render'],
)
app.include_router(
    adminAPI, dependencies=[Depends(current_active_superuser)], tags=['admin']
)
#  note: we can't secure the /data route because the otto preview is rendered into the <img> tag in the browser. Should find a workaround for this, but it is not critical.
app.mount('/data', StaticFiles(directory='data', html=True), name='data')
app.mount('/docs', StaticFiles(directory='site', html=True), name='docs')

# if request does not match the above api, try to return a StaticFiles match
app.mount('/', StaticFiles(directory='dist', html=True), name='static')


@app.on_event("startup")
async def on_startup():
    await init_beanie(
        database=get_db(),
        document_models=[
            User,
            renders.schema,
            renders.create_schema,
            renders.update_schema,
            projects.schema,
            projects.create_schema,
            projects.update_schema,
        ],
    )


if __name__ == '__main__':
    from uvicorn import run

    run(app, host='0.0.0.0', port=8000)
