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

    Still valid is the whole contract: an expired token is refused like any
    other, so this extends a session and cannot revive one. The SPA therefore
    renews *before* expiry, while it is in use, rather than after a 401 --
    which is what it used to do, and why sessions simply ended after an hour:
    by the time it asked, the token it asked with had already been refused.

    This also called `auth_backend.get_login_response(...)`, which has not
    existed on AuthenticationBackend for several major versions, so every
    refresh answered 500 until that was fixed.
    """
    return await auth_backend.login(strategy, user, response)
