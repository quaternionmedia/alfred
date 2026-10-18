"""Media: who may fetch a file, and what the library holds.

`media_access` is the half of contract M1 a route depends on: it admits a
request carrying a session (as every route did), or one carrying a valid,
unexpired signature for exactly the path it asks for (see `utils.signing`).
The routes that serve files -- `GET /render/{id}/download`, `GET
/videos/{name}` and `GET /preview/frames/{name}` -- depend on it instead of on
the session alone, so the browser can fetch them by itself from `<video>`,
`<img>` and `<a download>`.

It lives here rather than beside the signing code because it needs the
session dependency from the routes layer, and `utils` is imported by the
worker, which has no business importing routes.
"""

from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request

from alfred.config import DEV_SKIP_AUTH

from ..utils import signing
from .users import fastapi_users, get_dev_user

# The session's user, or None when the request has no valid session. The
# media routes cannot use `current_active_user`, which answers 401 before the
# route can look for a signature. Under the dev auth bypass every request has
# the dev user, as on every other route.
optional_user = (
    get_dev_user
    if DEV_SKIP_AUTH
    else fastapi_users.current_user(active=True, optional=True)
)

UNAUTHORIZED = 'Unauthorized'
REFUSED = {
    signing.EXPIRED: 'This media link has expired; ask for a new one',
    signing.INVALID: 'This media link is not valid',
}


@dataclass(frozen=True)
class MediaAccess:
    """How a request for a file was admitted.

    `signed` when it carried a good signature for its path: a capability the
    server issued after its own checks, so the route does not repeat them.
    Otherwise `user` is the session's user, and the route applies its usual
    ownership rules to them.
    """

    user: Optional[Any]
    signed: bool


async def media_access(request: Request, user=Depends(optional_user)) -> MediaAccess:
    """Admit a session, or a valid signature for this exact path; else 401."""
    params = request.query_params
    if 'sig' in params or 'exp' in params:
        problem = signing.check(
            signing.route_path(request.scope), params.get('exp'), params.get('sig')
        )
        if problem is None:
            return MediaAccess(user=user, signed=True)
        if user is None:
            raise HTTPException(status_code=401, detail=REFUSED[problem])
    if user is not None:
        return MediaAccess(user=user, signed=False)
    raise HTTPException(status_code=401, detail=UNAUTHORIZED)
