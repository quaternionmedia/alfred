from fastapi import APIRouter, Depends, Response, HTTPException, status
from .users import fastapi_users, auth_backend
from ..models import User, UserCreate, UserUpdate

from alfred.config import SECRET_KEY

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 90

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

auth = APIRouter()


auth.include_router(fastapi_users.get_auth_router(auth_backend), prefix='/jwt')
auth.include_router(fastapi_users.get_register_router(User, UserCreate))
auth.include_router(fastapi_users.get_reset_password_router())
auth.include_router(fastapi_users.get_verify_router(User))


@auth.post("/jwt/refresh")
async def refresh_jwt(
    response: Response, user=Depends(fastapi_users.current_user(active=True))
):
    return await auth_backend.get_login_response(user, response, fastapi_users)
