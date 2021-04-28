from fastapi import FastAPI, Depends
from starlette.staticfiles import StaticFiles
from uvicorn import run

from subprocess import run as bash
from auth import auth, get_current_active_user, User

from db import db
from users import users
from seed import seed, formToEdl

from routes import routes
from render import renderAPI
from emailer import emailAPI
from otto.main import app as ottoApi



app = FastAPI()

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

app.include_router(auth)
app.include_router(users)
app.include_router(routes, dependencies=[Depends(get_current_active_user)])
app.include_router(ottoApi, prefix='/otto', dependencies=[Depends(get_current_active_user)])
app.include_router(renderAPI, dependencies=[Depends(get_current_active_user)])
app.include_router(emailAPI, dependencies=[Depends(get_current_active_user)])

#  note: we can't secure the /data route because the otto preview is rendered into the <img> tag in the browser. Should find a workaround for this, but it is not critical.
app.mount('/data', StaticFiles(directory='data', html=True), name="data")

# if request does not match the above api, try to return a StaticFiles match
app.mount("/", StaticFiles(directory='dist', html=True), name="static")

if __name__ == '__main__':
    run(app, host='0.0.0.0', port=8000)
