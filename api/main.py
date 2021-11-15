from fastapi import FastAPI, Depends, Response
from fastapi.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles
from uvicorn import run


from subprocess import run as bash

from db import db
from config import DB_URL, DB_NAME
from auth import auth
from users import fastapi_users, current_active_user, current_active_superuser
from models import Template, TemplateUpdate, User, UserCreate, UserUpdate, UserDB

from seed import seed, formToEdl

from routes import routes
from render import renderAPI
from emailer import emailAPI
from template import templateAPI
from otto.main import app as ottoApi
import docs


app = FastAPI(
    title = docs.title,
    description = docs.description,
    version = docs.version,
    contact = docs.contact,
)
app.add_middleware(GZipMiddleware)


@app.on_event("startup")
async def seedDb():
    if not db.edls.count_documents({}):
        from seed import seed
        db.edls.insert_many(seed)
    if not db.projects.count_documents({}):
        from otto.defaults import sample_forms
        db.projects.insert_many(sample_forms)

@app.on_event('startup')
async def checkFonts():
    fonts = bash(['fc-list', '-f', '"%{family}-%{style}\n"'], capture_output=True).stdout.decode().replace('"', '').split('\n')
    results = []
    for f in fonts:
        if f:
            font = f.split('-')
            for fam in font[0].split(','):
                db.fonts.update_one({'family': fam.replace(' ', '-')}, {'$set': { 'style': [i.replace(' ', '-') for i in font[1].split(',')] }}, upsert=True)
    # db.fonts.update_many(results, upsert=True)

app.include_router(auth, prefix='/auth', tags=['auth'])
app.include_router(fastapi_users.get_users_router(), prefix="/users", tags=["users"])
app.include_router(templateAPI,
    dependencies=[Depends(current_active_user)])
app.include_router(routes, dependencies=[Depends(current_active_user)])
app.include_router(ottoApi, 
    prefix='/otto', 
    dependencies=[Depends(current_active_user)],
    tags=['otto'])
app.include_router(renderAPI, 
    dependencies=[Depends(current_active_user)],
    tags=['render'])
app.include_router(emailAPI, 
    dependencies=[Depends(current_active_user)],
    tags=['email'])

#  note: we can't secure the /data route because the otto preview is rendered into the <img> tag in the browser. Should find a workaround for this, but it is not critical.
app.mount('/data', StaticFiles(directory='data', html=True), name="data")

# if request does not match the above api, try to return a StaticFiles match
app.mount("/", StaticFiles(directory='dist', html=True), name="static")

if __name__ == '__main__':
    run(app, host='0.0.0.0', port=8000)
