from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from auth import User, get_current_active_user
from main import db

users = APIRouter()

@users.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@users.get("/users/me/items/")
async def read_own_items(current_user: User = Depends(get_current_active_user)):
    return [{"item_id": "Foo", "owner": current_user.username}]
