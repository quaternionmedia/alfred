from os import environ
from subprocess import run as bash
from textwrap import wrap

from beanie import init_beanie
from fastapi import Depends, FastAPI
from pydantic import ValidationError as PydanticValidationError
from starlette.concurrency import run_in_threadpool
from starlette.staticfiles import StaticFiles

from alfred import docs
from alfred.config import (
    DEV_SKIP_AUTH,
    DEV_USER_EMAIL,
    SEED_OWNER,
    STATIC_DIR,
    secret_key_problem,
)
from alfred.core import errors
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
from alfred.core.routes.users import (
    current_active_superuser,
    current_active_user,
    fastapi_users,
)
from alfred.core.utils import get_db
from alfred.core.utils.bucket import INVALID_ID
from alfred.core.utils.db import User
from alfred.core.utils.passwords import STARTUP_LINE as PASSWORD_HASHING

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
# A refusal's `code` beside its `detail` (`core/errors.py`, docs/api/errors.md).
errors.install(app)


@app.on_event('startup')
async def warnIfAuthIsDisabled():
    """The auth bypass's banner, every boot: the backstop for a deployment
    without ALFRED_PRODUCTION (docs/dev-auth.md#what-keeps-it-out-of-production).
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
async def namePasswordHashingOverride():
    """One line, every boot: alfred hashes passwords with its own copies of
    library security code (docs/api/auth.md#password-hashing)."""
    print(PASSWORD_HASHING, flush=True)


@app.on_event('startup')
async def warnIfSecretKeyIsWeak():
    """A banner, every boot, when the signing key is unset, empty or short."""
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
    # Awaited: an unawaited motor count is a Future, always truthy.
    if await db.Project.count_documents({}) == 0:
        from alfred.seed import owned_by, seed

        # Owned by SEED_OWNER: in development, the dev user.
        await db.Project.insert_many(owned_by(SEED_OWNER, seed))


def installed_fonts():
    """fontconfig's fonts, a `family-style` line each. Starts fc-list."""
    return (
        bash(['fc-list', '-f', '"%{family}-%{style}\n"'], capture_output=True)
        .stdout.decode()
        .replace('"', '')
        .split('\n')
    )


def font_styles(lines):
    """`(family, styles)` for each family each `family-style` line names, in
    order, with spaces as hyphens. A line can name several families, comma
    separated, and several styles the same way; a blank line names none."""
    found = []
    for line in lines:
        parts = line.split('-')
        if len(parts) < 2:
            continue
        styles = [i.replace(' ', '-') for i in parts[1].split(',')]
        found += [(fam.replace(' ', '-'), styles) for fam in parts[0].split(',')]
    return found


@app.on_event('startup')
async def checkFonts():
    db = get_db()
    # In the thread pool, like every process the api starts; no exceptions.
    fonts = await run_in_threadpool(installed_fonts)
    found = font_styles(fonts)
    for family, styles in found:
        await db.fonts.update_one(
            {'family': family},
            {'$set': {'style': styles}},
            upsert=True,
        )
    # Drop families fontconfig no longer lists: the collection outlives the image.
    await db.fonts.delete_many({'family': {'$nin': [family for family, _ in found]}})


@app.exception_handler(PydanticValidationError)
async def malformedIdentifier(request, exc):
    """An unparseable id in the path (`/project/undefined`) is a 422
    `invalid_id`, not a 500; a well-formed id that matches nothing stays 404.

    Narrow on purpose: any other ValidationError is re-raised, so a
    server-side model mistake stays a loud 500.
    """
    if not _isIdentifierParseError(exc):
        raise exc
    # The refusal the routes that check an id themselves answer, code and all.
    return await errors.answer_refusal(request, INVALID_ID)


def _isIdentifierParseError(exc):
    # A bare id parsed alone (no field in its loc), refused by PydanticObjectId.
    errors = exc.errors(include_url=False)
    return bool(errors) and all(
        not error['loc'] and 'PydanticObjectId' in error['msg'] for error in errors
    )


app.include_router(authAPI, prefix='/auth', tags=['auth'])

# `/healthz` answers without a session, for container health checks; `/health`
# requires one, and says whether a renderer is running (contract M3).
app.include_router(healthAPI, tags=['health'])

if DEV_SKIP_AUTH:
    # Shadows fastapi-users' /users/me, so registered before it: overriding
    # the dependency does not reach that route (docs/dev-auth.md#what-it-does).
    from alfred.core.routes.users import get_dev_user

    @app.get('/users/me', response_model=UserRead, tags=['users'])
    async def dev_users_me(user: User = Depends(get_dev_user)):
        # Built field by field: UserRead.id is a required str, which the
        # document does not offer by that name (a 500 otherwise).
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

# Files a browser fetches by itself (`<video src>`, `<img src>`), with no
# Authorization header: a session, or a signed URL for that path (contract M1).
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
