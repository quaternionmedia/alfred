from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from auth import User, get_current_active_user
from db import db

users = APIRouter()

@users.post('/register')
async def registerUser(form_data: OAuth2PasswordRequestForm = Depends()):
    if (db.users.find({'username': form_data.username}).count()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User already exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    else:
        db.users.insert_one({
        'username': form_data.username,
        'first_name': form_data.first_name,
        'last_name': form_data.last_name,
        'hashed_password': pwd_context.hash(form_data.password),
        'email': form_data.email,
        })

@users.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@users.get("/users/me/items/")
async def read_own_items(current_user: User = Depends(get_current_active_user)):
    return [{"item_id": "Foo", "owner": current_user.username}]
