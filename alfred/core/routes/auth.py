from fastapi import APIRouter, Depends, Response, HTTPException, status
from .users import fastapi_users, auth_backend
from ..models import UserRead, UserCreate

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 90

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

auth = APIRouter()


auth.include_router(fastapi_users.get_auth_router(auth_backend), prefix='/jwt')
auth.include_router(fastapi_users.get_register_router(UserRead, UserCreate))
auth.include_router(fastapi_users.get_reset_password_router())
auth.include_router(fastapi_users.get_verify_router(UserRead))


@auth.post("/jwt/refresh")
async def refresh_jwt(
    response: Response,
    user=Depends(fastapi_users.current_user(active=True)),
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
