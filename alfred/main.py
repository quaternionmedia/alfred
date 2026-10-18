from os import environ
from subprocess import run as bash
from textwrap import wrap

from beanie import init_beanie
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.staticfiles import StaticFiles

from alfred import docs
from alfred.config import (
    DEV_SKIP_AUTH,
    DEV_USER_EMAIL,
    SEED_OWNER,
    STATIC_DIR,
    secret_key_problem,
)
from alfred.core.models.users import UserRead, UserUpdate
from alfred.core.responses import MediaAwareGZipMiddleware
from alfred.core.routes import (
    ProjectAPI,
    RenderAPI,
    adminAPI,
    audioAPI,
    authAPI,
    captionsAPI,
    demoAPI,
    fontAPI,
    healthAPI,
    issueAPI,
    mediaAPI,
    previewAPI,
    previewFrameAPI,
    renderFileAPI,
    templateAPI,
    videoAPI,
    videoFileAPI,
)

# from alfred.core.utils.db import deOid
from alfred.core.routes.users import (
    current_active_superuser,
    current_active_user,
    fastapi_users,
)

# from otto.main import app as ottoApi
from alfred.core.utils import get_db
from alfred.core.utils.db import User

app = FastAPI(
    title=docs.title,
    description=docs.description,
    version=docs.version,
    contact=docs.contact,
    openapi_tags=docs.tags_metadata,
    docs_url='/api',
)
# GZip for JSON and the SPA's assets; media and byte ranges go out as they are
# (see `responses/compression.py`).
app.add_middleware(MediaAwareGZipMiddleware)


@app.on_event('startup')
async def warnIfAuthIsDisabled():
    """Say so, every boot, unmissably.

    A bypass that runs quietly is one that reaches an environment nobody
    meant it to. config.py refuses to combine this with ALFRED_PRODUCTION, so
    this cannot be a production process -- but ALFRED_PRODUCTION is only set
    by production.yml, and a deployment that forgets it would get no such
    refusal. The banner is the second line of defence.
    """
    if DEV_SKIP_AUTH:
        line = '=' * 72
        print(line, flush=True)
        print('  AUTHENTICATION IS DISABLED (ALFRED_DEV_SKIP_AUTH)', flush=True)
        print(
            f'  Every request is served as {DEV_USER_EMAIL}, a superuser.', flush=True
        )
        print('  Local development only. Never expose this process.', flush=True)
        print(line, flush=True)


@app.on_event('startup')
async def warnIfSecretKeyIsWeak():
    """Say so, every boot, when the signing key will not do.

    The same treatment as the auth bypass banner, for the same reason: a
    process that starts successfully looks healthy, and a missing or short
    key is invisible until a login fails -- or until somebody forges one.
    Read from the environment at startup, the same place config.py read it.
    """
    problem = secret_key_problem(environ)
    if problem:
        line = '!' * 72
        print(line, flush=True)
        print('  THE TOKEN SIGNING KEY IS NOT SAFE TO USE', flush=True)
        for text in wrap(problem, 68):
            print(f'  {text}', flush=True)
        print(line, flush=True)


@app.on_event('startup')
async def seedDb():
    db = get_db()
    # `count_documents` is a coroutine on a motor handle. Calling it without
    # awaiting returned a Future, which is always truthy, so `if not ...`
    # never fired and this block never ran. The import was also `from seed`,
    # which only resolves with alfred/ as the working directory.
    if await db.Project.count_documents({}) == 0:
        from alfred.seed import owned_by, seed

        # Owned like any other project. In development that is the dev user,
        # so ALFRED_DEV_SKIP_AUTH still opens onto them; see SEED_OWNER.
        await db.Project.insert_many(owned_by(SEED_OWNER, seed))


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


@app.exception_handler(PydanticValidationError)
async def malformedIdentifier(request, exc):
    """Turn an unparseable path identifier into 422 rather than 500.

    `GET /project/undefined` returned 500. fastapi-crudrouter hands the raw
    path segment to beanie's `Document.get`, which parses it into a
    PydanticObjectId and raises; nothing caught it. The frontend does send
    `undefined` -- the editor routes read a `project` query parameter that is
    not always there -- so this was reachable from the UI, and a 500 says the
    server broke when the request was malformed.

    A well-formed id that matches nothing already returned 404 correctly. This
    only covers the unparseable case, and answers 422 rather than 404 to keep
    "you sent something that is not an id" distinguishable from "that id does
    not exist" -- the frontend can act on the difference.

    Deliberately narrow: it re-raises anything that is not an identifier parse
    failure. A blanket handler for pydantic's ValidationError would turn every
    server-side model mistake into a client error, which is exactly the kind
    of 500-shaped bug that should stay loud. Response validation is unaffected
    either way -- FastAPI's ResponseValidationError does not inherit from
    pydantic's ValidationError.
    """
    if not _isIdentifierParseError(exc):
        raise exc
    return JSONResponse(
        status_code=422,
        content={'detail': 'Not a valid identifier'},
    )


def _isIdentifierParseError(exc):
    model = getattr(exc, 'model', None)
    return 'PydanticObjectId' in str(getattr(model, '__name__', model))


app.include_router(authAPI, prefix='/auth', tags=['auth'])

# `/healthz` answers without a session, for container health checks; `/health`
# requires one, and says whether a renderer is running (contract M3).
app.include_router(healthAPI, tags=['health'])

if DEV_SKIP_AUTH:
    # Registered before the fastapi-users router so this match wins; FastAPI
    # resolves routes in registration order.
    #
    # Swapping `current_active_user` is not enough to cover /users/me.
    # get_users_router builds its own dependency internally from the
    # authenticator, so it is a different callable from the one this module
    # exports -- and dependency_overrides keys on identity, so that does not
    # reach it either. Without this route the SPA's probe 401s and the login
    # screen comes back, with every other endpoint open. Shadowing the one
    # route is the smallest thing that makes the bypass coherent.
    from alfred.core.routes.users import get_dev_user

    @app.get('/users/me', response_model=UserRead, tags=['users'])
    async def dev_users_me(user: User = Depends(get_dev_user)):
        # Built explicitly rather than returned as a document.
        #
        # Returning the Beanie document worked while UserRead.id was optional
        # and serialised as null. Once id became a required string -- the fix
        # for /users/me handing back `{}` -- FastAPI could not find it on the
        # document by field name and answered 500 with "field required". The
        # bypass then failed at exactly the endpoint the SPA probes to decide
        # whether it is logged in, so the app sat on the login screen with
        # every other route wide open.
        return UserRead(
            id=str(user.id),
            email=user.email,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            is_verified=user.is_verified,
            first_name=user.first_name,
            birthdate=getattr(user, 'birthdate', None),
            address=getattr(user, 'address', None),
        )


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
# A project's captions (contract K2), scoped to the caller like the project.
app.include_router(
    captionsAPI, dependencies=[Depends(current_active_user)], tags=['captions']
)

app.include_router(fontAPI, dependencies=[Depends(current_active_user)], tags=['font'])
app.include_router(
    templateAPI, dependencies=[Depends(current_active_user)], tags=['template']
)
app.include_router(demoAPI, dependencies=[Depends(current_active_user)], tags=['demo'])
app.include_router(
    videoAPI, dependencies=[Depends(current_active_user)], tags=['video']
)
app.include_router(
    mediaAPI, dependencies=[Depends(current_active_user)], tags=['media']
)
# How a library file sounds, from the audio engine; seen by whoever sees the
# library.
app.include_router(
    audioAPI, dependencies=[Depends(current_active_user)], tags=['media']
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

# Files a browser fetches by itself -- `<video src>`, `<img src>`, `<a
# download>` -- which cannot carry the session's Authorization header. Each
# route depends on `media_access` instead of the session alone: a session, or
# a signed URL for exactly that path (contract M1).
#
# This replaces the unauthenticated /data mount, which existed because the EDL
# preview's frame had to reach an `<img>`. Everything it served was public to
# anyone with the name: preview frames, and in its time local deliveries and
# the engine's downloads. Nothing reads from it any more.
app.include_router(renderFileAPI, tags=['render'])
app.include_router(videoFileAPI, tags=['video'])
app.include_router(previewFrameAPI, prefix='/preview', tags=['preview'])

# if request does not match the above api, try to return a StaticFiles match
app.mount('/', StaticFiles(directory=STATIC_DIR, html=True), name='dist')


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
