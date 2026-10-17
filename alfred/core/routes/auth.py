from fastapi import APIRouter, Depends, HTTPException, Response, status

from alfred import config

from ..models import UserCreate, UserRead
from .users import auth_backend, current_active_user, fastapi_users

REGISTRATION_CLOSED = (
    'Registration is closed on this server. Ask an administrator for an account.'
)


async def registration_is_open():
    """Refuse to create accounts unless this server accepts them.

    A dependency on the register route rather than leaving the route out, for
    two reasons. Left out, `POST /auth/register` falls through to the static
    mount and answers 405 -- which says "wrong method", not "closed", and the
    SPA could not tell a misconfigured client from a deliberate policy. And
    dependencies resolve before the body is validated, so a closed server
    answers 403 to any registration attempt without first explaining what a
    valid one would look like.

    Reads the setting through the module at request time, so the tests can
    open and close registration without restarting the app.
    """
    if not config.ALLOW_REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=REGISTRATION_CLOSED
        )


auth = APIRouter()


auth.include_router(fastapi_users.get_auth_router(auth_backend), prefix='/jwt')
auth.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    dependencies=[Depends(registration_is_open)],
)
auth.include_router(fastapi_users.get_reset_password_router())
auth.include_router(fastapi_users.get_verify_router(UserRead))


@auth.post("/jwt/refresh")
async def refresh_jwt(
    response: Response,
    user=Depends(current_active_user),
    strategy=Depends(auth_backend.get_strategy),
):
    """Issue a fresh token to a caller whose current one is still valid.

    This called `auth_backend.get_login_response(user, response, fastapi_users)`,
    which has not existed on AuthenticationBackend for several major versions --
    it carries `login` and `logout` and nothing else. So every refresh answered
    500, and the frontend calls this on *every* 401: `auth()` in Login.js
    catches an unauthorised response, tries to refresh, and only then gives up
    and redirects. A session reaching its expiry therefore failed with a server
    error rather than renewing, and the one path that exists to keep somebody
    logged in was the one path that could not work.
    """
    return await auth_backend.login(strategy, user, response)
