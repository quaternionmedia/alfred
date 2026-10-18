"""Short-lived capability URLs for media the browser fetches by itself.

Contract M1. A `<video src>`, an `<img src>` or an `<a download>` is a request
the browser makes on its own, and it carries no Authorization header. So every
file route that needs a session answered those elements 401, and the SPA had
to fetch whole files with the token and hand the bytes over as object URLs --
no streaming, every render held in memory, and a public `/data` mount for the
frames it could not fetch that way.

A signed URL is the request the browser can make: `<path>?exp=<unix
seconds>&sig=<signature>`, where the signature is an HMAC-SHA256 over
`"GET\\n<path>\\n<exp>"`, urlsafe base64 without padding, keyed by
HMAC-SHA256(ALFRED_SECRET_KEY, b"alfred-media-v1"). Holding one is permission
to GET exactly that path until `exp`, and nothing else: the routes issue them
only after their own authentication and ownership checks have passed.

The key is derived rather than the secret used directly, so a media URL can
never be confused with any other value the same secret signs (session tokens,
reset tokens), and the context string versions the scheme. With no secret
configured -- the development stub leaves it empty -- the key is a random one
of the process's own (see `_PROCESS_KEY`).

The path signed is the decoded path, as the routes see it; `media_url` returns
it percent-encoded, which is the form a browser sends and the server decodes
back. Clients treat the URL as opaque.
"""

import hmac
import secrets
from base64 import urlsafe_b64encode
from hashlib import sha256
from math import ceil
from time import time
from typing import Optional
from urllib.parse import quote

from alfred import config

KEY_CONTEXT = b'alfred-media-v1'

# The key used when ALFRED_SECRET_KEY is empty, as the development stub
# committed to this repository leaves it: random, and this process's alone.
# Its URLs work until the api restarts, and only in the process that issued
# them -- but nobody can forge one, which signing with the empty secret would
# allow. A configured key is never replaced by this.
_PROCESS_KEY = secrets.token_bytes(32)
_warned = False

# Expiries are rounded up to a whole minute, so every URL issued for a path in
# the same minute is the same URL. A browser caches by URL: without this, each
# listing or status poll would hand out a new address for the same file, and
# an `<img>` or `<video>` given it would fetch the file again. The cost is a
# URL living up to a minute longer than the TTL asked for.
EXPIRY_STEP = 60

# What a refused signature was, for the caller's error message.
EXPIRED = 'expired'
INVALID = 'invalid'


def _key() -> bytes:
    """The media key: derived from ALFRED_SECRET_KEY, or this process's own."""
    global _warned
    secret = config.SECRET_KEY
    if secret:
        return hmac.new(secret.encode(), KEY_CONTEXT, sha256).digest()
    if not _warned:
        _warned = True
        print(
            'ALFRED_SECRET_KEY is empty: media URLs are signed with a key of '
            "this process's own, and stop working when it restarts.",
            flush=True,
        )
    return _PROCESS_KEY


def signature(path: str, exp: int) -> str:
    """The signature of a GET for `path` that works until `exp`."""
    message = f'GET\n{path}\n{exp}'.encode()
    digest = hmac.new(_key(), message, sha256).digest()
    return urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


def expiry(ttl: Optional[int] = None, now: Optional[float] = None) -> int:
    """When a URL issued now should stop working: at least `ttl` from now."""
    ttl = config.MEDIA_URL_TTL if ttl is None else ttl
    now = time() if now is None else now
    return int(ceil((now + ttl) / EXPIRY_STEP) * EXPIRY_STEP)


def media_url(path: str, ttl: Optional[int] = None, now: Optional[float] = None) -> str:
    """A URL that lets whoever holds it GET `path` for `ttl` seconds.

    `path` is the server path as a route sees it, starting with `/`, e.g.
    `/render/<id>/download`. Only call this once the caller has passed the
    route's own checks: the URL is a bearer capability.
    """
    exp = expiry(ttl, now)
    return f'{quote(path)}?exp={exp}&sig={signature(path, exp)}'


def check(path: str, exp, sig, now: Optional[float] = None) -> Optional[str]:
    """Why a signed request for `path` is refused, or None if it is good.

    `INVALID` for a missing, malformed or wrong signature -- including a good
    signature for a different path -- and `EXPIRED` for a right one whose time
    is up. Compared in constant time.
    """
    if not exp or not sig or not isinstance(exp, str) or not isinstance(sig, str):
        return INVALID
    # One spelling per expiry: decimal digits, no sign, no leading zeros, and
    # not absurdly long (Python refuses to read a number of thousands of
    # digits, which would otherwise be a 500).
    if len(exp) > 12 or not exp.isascii() or not exp.isdigit():
        return INVALID
    if exp != str(int(exp)):
        return INVALID
    if not hmac.compare_digest(signature(path, int(exp)), sig):
        return INVALID
    if int(exp) < (time() if now is None else now):
        return EXPIRED
    return None


def route_path(scope) -> str:
    """The path a request was for, as the app's routes match it.

    The decoded path, without any `root_path` a proxy mounted the app under
    -- the same path `media_url` was given when the URL was issued.
    """
    path = scope['path']
    root = scope.get('root_path') or ''
    if root and path.startswith(root) and path[len(root) : len(root) + 1] == '/':
        return path[len(root) :]
    return path
