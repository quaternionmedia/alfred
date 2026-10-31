from fastapi import APIRouter, Depends, HTTPException, status

from alfred import config

from ..models import UserCreate, UserRead
from .users import auth_backend, current_active_user, fastapi_users

REGISTRATION_CLOSED = (
    'Registration is closed on this server. Ask an administrator for an account.'
)


async def registration_is_open():
    """Refuse to create accounts unless this server accepts them: 403.

    A dependency, not a route left out (which would answer the static mount's
    405), and resolved before the body is validated. Read at request time, so
    tests can open and close registration.
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
    user=Depends(current_active_user),
    strategy=Depends(auth_backend.get_strategy),
):
    """Issue a fresh token to a caller whose current one is still valid.

    An expired token is refused like any other, so this extends a session and
    cannot revive one: the SPA renews *before* expiry, while it is in use.
    """
    return await auth_backend.login(strategy, user)
