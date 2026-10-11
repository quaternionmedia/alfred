"""Malformed path identifiers are a client error, not a server error.

`GET /project/undefined` and `GET /render/undefined` both answered 500. The
editor really does send that: its routes read a `project` query parameter that
is not always present, and `'/project/' + undefined` is a string the browser
will happily request. So the two most-used views produced server errors as part
of normal navigation.

The two routes failed for different reasons and needed different fixes, which
is the thing most worth pinning here. The project routes go through
fastapi-crudrouter into beanie, which raises pydantic's ValidationError. The
render download route calls `ObjectId(...)` directly, which raises bson's
InvalidId -- a different exception hierarchy entirely, so the handler that
covers the first does nothing for the second.
"""

import pytest
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException
from pydantic import ValidationError

from alfred.main import _isIdentifierParseError
from alfred.core.utils.bucket import INVALID_ID, NOT_FOUND


class TestTheHandlerRecognisesIdentifierErrors:
    def test_an_objectid_parse_failure_is_recognised(self):
        """Built by failing a real parse, not by hand.

        A hand-rolled ValidationError would only prove the predicate matches
        whatever this test constructs. Raising through beanie's own parsing is
        what makes this evidence about the exception the application actually
        sees.
        """
        from beanie import PydanticObjectId
        from pydantic import parse_obj_as

        # pydantic's own API rather than beanie's internal helper: the helper
        # moved between the beanie version installed here and the one in the
        # API image, and a test that pins an internal import path fails on the
        # wrong thing when a dependency reorganises.
        with pytest.raises(ValidationError) as excinfo:
            parse_obj_as(PydanticObjectId, 'undefined')

        assert _isIdentifierParseError(excinfo.value)

    def test_an_unrelated_validation_error_is_not_recognised(self):
        """The handler must not turn server-side model bugs into 422s.

        This is the failure mode that made a blanket handler wrong: a
        ValidationError from constructing a response model means the server
        got something wrong, and reporting that as a client error hides it.
        """
        from pydantic import BaseModel

        class Unrelated(BaseModel):
            count: int

        with pytest.raises(ValidationError) as excinfo:
            Unrelated(count='not a number')

        assert not _isIdentifierParseError(excinfo.value)

    def test_response_validation_errors_are_a_different_hierarchy(self):
        """Documents why the handler cannot catch response failures.

        FastAPI's ResponseValidationError does not inherit from pydantic's
        ValidationError, so registering a handler for the latter leaves
        response validation alone. If that ever changes, the handler starts
        converting server bugs into 422s and this test is the warning.
        """
        from fastapi.exceptions import ResponseValidationError

        assert not issubclass(ResponseValidationError, ValidationError)


class TestTheRenderRouteGuardsSeparately:
    """bson's InvalidId is not pydantic's ValidationError."""

    def test_bson_raises_its_own_error_type(self):
        with pytest.raises(InvalidId):
            ObjectId('undefined')

    def test_that_error_is_invisible_to_the_pydantic_handler(self):
        """Why bucket.py needs a guard of its own.

        The signed-URL route calls ObjectId() directly rather than going
        through beanie, so main.py's handler never sees the failure. Without
        the explicit check in generate_signed_url, /render/undefined stays a
        500 while /project/undefined is fixed -- which is exactly what
        happened on the first pass.
        """
        assert not issubclass(InvalidId, ValidationError)

    def test_the_guard_uses_the_same_status_as_the_project_routes(self):
        """Both malformed-identifier paths answer 422, not one each way."""
        assert isinstance(INVALID_ID, HTTPException)
        assert INVALID_ID.status_code == 422

    def test_a_missing_item_stays_distinguishable_from_a_malformed_one(self):
        """404 and 422 mean different things and the frontend can act on it.

        A well-formed id that matches no row is 404; an id that is not an id
        is 422. Collapsing them would leave the editor unable to tell "this
        project was deleted" from "I built a URL out of undefined".
        """
        assert NOT_FOUND.status_code == 404
        assert INVALID_ID.status_code != NOT_FOUND.status_code

    @pytest.mark.parametrize(
        'candidate,valid',
        [
            ('undefined', False),
            ('null', False),
            ('', False),
            ('[object Object]', False),
            ('deadbeefdeadbeefdeadbeef', True),
            ('6a76a53effdcf46c9c285cf5', True),
        ],
    )
    def test_is_valid_agrees_with_what_the_route_accepts(self, candidate, valid):
        """`[object Object]` is in this list because the app really sent it.

        A broken asset import put that string in an img src, and the browser
        requested it as a path. It is a reminder that the values reaching a
        route are not limited to the ones a developer would think to type.
        """
        assert ObjectId.is_valid(candidate) is valid
