from fastapi import APIRouter, Depends, Response, HTTPException, status
from users import fastapi_users, jwt_authentication

from config import SECRET_KEY

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 90

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

auth = APIRouter()


auth.include_router(
    fastapi_users.get_auth_router(jwt_authentication), prefix='/jwt'
)
auth.include_router(
    fastapi_users.get_register_router()
)
auth.include_router(
    fastapi_users.get_reset_password_router(),
)
auth.include_router(
    fastapi_users.get_verify_router(),
)

@auth.post("/jwt/refresh")
async def refresh_jwt(response: Response, user=Depends(fastapi_users.current_user(active=True))):
    return await jwt_authentication.get_login_response(user, response)