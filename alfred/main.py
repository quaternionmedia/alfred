from fastapi import FastAPI, Depends
from fastapi.middleware.gzip import GZipMiddleware
from starlette.staticfiles import StaticFiles

from subprocess import run as bash

from alfred import db, client

from core.routes import authAPI
from core.routes import routesAPI
from core.routes import renderAPI
from core.routes import emailAPI
from core.routes import adminAPI
from otto.main import app as ottoApi

from fastapi_crudrouter import MotorCRUDRouter

from core.models import Template, TemplateUpdate, User, UserCreate, UserUpdate, UserDB
from core.routes.users import fastapi_users, current_active_user, current_active_superuser

from seed import seed
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

templateAPI = MotorCRUDRouter(
    schema = Template,
    client = client,
    create_schema = Template,
    update_schema = TemplateUpdate
)
app.include_router(templateAPI)
app.include_router(authAPI, prefix='/auth', tags=['auth'])
app.include_router(fastapi_users.get_users_router(), prefix="/users", tags=["users"])
app.include_router(templateAPI,
    dependencies=[Depends(current_active_user)])
app.include_router(routesAPI, dependencies=[Depends(current_active_user)])
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
app.include_router(adminAPI, 
    dependencies=[Depends(current_active_superuser)],
    tags=['admin'])
#  note: we can't secure the /data route because the otto preview is rendered into the <img> tag in the browser. Should find a workaround for this, but it is not critical.
app.mount('/data', StaticFiles(directory='data', html=True), name="data")

# if request does not match the above api, try to return a StaticFiles match
app.mount("/", StaticFiles(directory='dist', html=True), name="static")

if __name__ == '__main__':
    from uvicorn import run
    run(app, host='0.0.0.0', port=8000)
