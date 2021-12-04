from fastapi import FastAPI, Depends
from typing import Optional
from fastapi.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles

from subprocess import run as bash

from core.routes import authAPI
from core.routes import videoAPI
from core.routes import renderAPI
from core.routes import issueAPI
from core.routes import adminAPI
from core.routes import fontAPI
from core.routes import ProjectAPI
from otto.main import app as ottoApi
from core.utils import get_db
from core.routes.render import deOid

from core.routes.users import fastapi_users, current_active_user, current_active_superuser

from seed import seed
import docs


app = FastAPI(
    title = docs.title,
    description = docs.description,
    version = docs.version,
    contact = docs.contact,
    openapi_tags=docs.tags_metadata,
    docs_url = '/api',
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
    fonts = bash(['fc-list', '-f', '"%{family}-%{style}\n"'], capture_output=True).stdout.decode().replace('"', '').split('\n')
    results = []
    for f in fonts:
        if f:
            font = f.split('-')
            for fam in font[0].split(','):
                await db.fonts.update_one({'family': fam.replace(' ', '-')}, {'$set': { 'style': [i.replace(' ', '-') for i in font[1].split(',')] }}, upsert=True)
    # db.fonts.update_many(results, upsert=True)

app.include_router(authAPI, prefix='/auth', tags=['auth'])
app.include_router(fastapi_users.get_users_router(), prefix='/users', tags=['users'])

projects = ProjectAPI()
app.include_router(projects,
    dependencies=[Depends(current_active_user)])

app.include_router(fontAPI,
    dependencies=[Depends(current_active_user)], tags=['font'])
app.include_router(videoAPI, 
    dependencies=[Depends(current_active_user)], tags=['video'])
app.include_router(ottoApi, 
    prefix='/otto', 
    dependencies=[Depends(current_active_user)],
    tags=['otto'])
app.include_router(renderAPI, 
    dependencies=[Depends(current_active_user)],
    tags=['render'])
app.include_router(issueAPI, 
    prefix='/render',
    dependencies=[Depends(current_active_user)],
    tags=['render'])
app.include_router(adminAPI, 
    dependencies=[Depends(current_active_superuser)],
    tags=['admin'])
#  note: we can't secure the /data route because the otto preview is rendered into the <img> tag in the browser. Should find a workaround for this, but it is not critical.
app.mount('/data', StaticFiles(directory='data', html=True), name='data')
app.mount('/docs', StaticFiles(directory='site', html=True), name='docs')

# if request does not match the above api, try to return a StaticFiles match
app.mount('/', StaticFiles(directory='dist', html=True), name='static')

if __name__ == '__main__':
    from uvicorn import run
    run(app, host='0.0.0.0', port=8000)
