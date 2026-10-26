from datetime import datetime
from typing import Optional

from beanie import PydanticObjectId
from fastapi_users import schemas
from pydantic import field_validator


class UserRead(schemas.BaseUser[PydanticObjectId]):
    # Declared explicitly even though the base is parameterised with the same
    # type. Subscripting the generic left `UserRead.__fields__['id'].type_` as
    # `typing.Any`, so pydantic had no encoder for an ObjectId and FastAPI's
    # jsonable_encoder fell back to `vars()` -- which for an ObjectId is `{}`.
    #
    # `GET /users/me` therefore answered `{"id": {}}` to every authenticated
    # caller, and `{"id": null}` under the dev auth bypass, where the document
    # is built by field name and `id` is aliased `_id`. The stored user has a
    # real ObjectId in both cases; nothing downstream could read it.
    id: str
    first_name: str
    birthdate: Optional[datetime] = None
    address: Optional[str] = None

    @field_validator('id', mode='before')
    @classmethod
    def _identifier_as_string(cls, value):
        """Carry the id out as a string, on the field itself.

        Two earlier attempts did not survive the trip. Declaring
        `id: PydanticObjectId` fixed the type -- the generic base left it as
        `typing.Any` -- but FastAPI serialises through jsonable_encoder, which
        has no rule for a bson.ObjectId subclass and falls back to
        `vars(value)`; an ObjectId's `vars()` is `{}`. Adding
        `json_encoders = {ObjectId: str}` to Config fixed the model in
        isolation and changed nothing on the route, because FastAPI clones a
        response model into a fresh class and the clone does not carry Config.

        A before-validator is part of the field, so it survives the cloning. The
        wire format is unchanged from what callers should always have seen: a
        24-character hex string.
        """
        return str(value) if value is not None else value


class UserCreate(schemas.BaseUserCreate):
    first_name: str
    birthdate: Optional[datetime] = None
    address: Optional[str] = None


class UserUpdate(schemas.BaseUserUpdate):
    first_name: Optional[str] = None
    birthdate: Optional[datetime] = None
    address: Optional[str] = None
