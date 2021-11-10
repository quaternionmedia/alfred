from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.param_functions import Form
from auth import User, UserInDB, get_current_active_user, pwd_context
from db import db


class RegisterForm(OAuth2PasswordRequestForm):
    def __init__(
        self,
        username: str = Form(...),
        password: str = Form(...),
        email: str = Form(...)
    ):
        self.email = email
        self.username = username
        self.password = password

users = APIRouter()

@users.post('/register')
async def registerUser(form_data: RegisterForm = Depends()):
    """# Regsister User
    Create a new user in the database"""
    c = db.users.find({'username': form_data.username})
    if c.count():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User already exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    else:
        db.users.insert_one(UserInDB(
            username=form_data.username,
            hashed_password=pwd_context.hash(form_data.password),
            email=form_data.email,
            verified=False,
        ).dict())
        # TODO: send email verification here

@users.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """# Who Am I
    Returns a `User` object with the current logged in user."""
    return current_user


@users.get("/users/{username}/", response_model=User)
async def read_user(username: str, current_user: User = Depends(get_current_active_user)):
    """# Read user
    Returns a `User` object for the requested username"""
    # TODO: Manage scopes and permissions
    return db.users.find_one({'username': username})
