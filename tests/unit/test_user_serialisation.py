"""`/users/me` returns an id a caller can use.

It did not. Every authenticated request got `{"id": {}}`, and the dev auth
bypass got `{"id": null}`, while the stored user had a real ObjectId in both
cases. Nothing downstream could identify the current user.

Three fixes were needed and only the third worked, so this tests the outcome
rather than any one of them:

1. `UserRead.__fields__['id'].type_` was `typing.Any` -- subscripting the
   generic base did not bind the parameter. Declaring `id` explicitly fixed
   the type and nothing else.
2. FastAPI serialises through `jsonable_encoder`, which has no rule for a
   `bson.ObjectId` subclass and falls back to `vars(value)`. An ObjectId's
   `vars()` is `{}`. Adding `json_encoders` to Config fixed the model in
   isolation and changed nothing on the route: FastAPI clones a response model
   into a fresh class, and the clone does not carry Config.
3. A pre-validator belongs to the field, so it survives the cloning.
"""

import re

from beanie import PydanticObjectId
from fastapi.encoders import jsonable_encoder
from fastapi.utils import create_cloned_field

from alfred.core.models.users import UserRead

OBJECT_ID = re.compile(r'^[0-9a-f]{24}$')


def _a_user(**overrides):
    fields = dict(
        id=PydanticObjectId(),
        email='someone@example.com',
        is_active=True,
        is_superuser=False,
        is_verified=True,
        first_name='Someone',
    )
    fields.update(overrides)
    return fields


class TestTheIdSurvivesSerialisation:
    def test_the_model_keeps_the_identifier(self):
        fields = _a_user()
        user = UserRead(**fields)
        assert user.id == str(fields['id'])

    def test_jsonable_encoder_produces_a_hex_string(self):
        """The step that turned an ObjectId into `{}`."""
        encoded = jsonable_encoder(UserRead(**_a_user()))
        assert isinstance(encoded['id'], str)
        assert OBJECT_ID.match(encoded['id']), f'not an object id: {encoded["id"]!r}'

    def test_the_encoded_id_matches_the_one_supplied(self):
        fields = _a_user()
        encoded = jsonable_encoder(UserRead(**fields))
        assert encoded['id'] == str(fields['id'])

    def test_it_survives_fastapis_response_model_cloning(self):
        """The step that defeated the Config-based fix.

        FastAPI rebuilds a response model into a new class before using it.
        Config -- and so `json_encoders` -- does not come along. Anything that
        makes this work has to live on the field, which is why the fix is a
        validator. Without this test the Config version looks correct in every
        unit test and still returns `{}` from the running server.
        """
        cloned = create_cloned_field(UserRead.__fields__['id'])
        value, error = cloned.validate(PydanticObjectId(), {}, loc=('id',))
        assert error is None, f'cloned field rejected an ObjectId: {error}'
        assert isinstance(value, str)
        assert OBJECT_ID.match(value)


class TestTheDevBypassSerialisesTheSameWay:
    def test_an_id_supplied_as_a_string_is_unchanged(self):
        """The bypass path built the model by field name and produced null.

        Whatever the source, the wire format is one hex string.
        """
        raw = '6a76a53effdcf46c9c285cf5'
        assert jsonable_encoder(UserRead(**_a_user(id=raw)))['id'] == raw

    def test_the_field_is_not_optional(self):
        """`null` was one of the two broken outputs; it must not be reachable.

        A user without an id is not a user, and an Optional field would let the
        null case come back quietly.
        """
        assert UserRead.__fields__['id'].required
