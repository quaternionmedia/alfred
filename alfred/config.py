from os import environ

PRODUCTION = environ.get('ALFRED_PRODUCTION')

SECRET_KEY = environ.get('ALFRED_SECRET_KEY')


def _truthy(value):
    """Explicit opt-in only.

    Deliberately not `bool(environ.get(...))`, which treats `ALFRED_DEV_SKIP_AUTH=0`
    and `=false` as on -- the two spellings someone reaches for to turn a flag
    off. For a flag that disables authentication, the failure has to be in the
    direction of staying locked.
    """
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _given(value):
    """Whether a variable was actually set to something.

    Empty counts as unset. Compose passes a host variable through as
    `X=${X:-}`, which hands the container an empty string for a variable
    nobody set -- and an empty string must mean "use the default", not
    "explicitly off".
    """
    return value is not None and str(value).strip() != ''


def resolve_allow_registration(env):
    """Whether `POST /auth/register` may create accounts.

    Registration was mounted unconditionally, so anyone who could reach a
    production server could give themselves an account on it. Open by default
    in development, where registering is how you get a user at all, and closed
    by default under ALFRED_PRODUCTION, where accounts are handed out rather
    than taken.

    ALFRED_ALLOW_REGISTRATION overrides the default in either direction,
    parsed exactly like ALFRED_DEV_SKIP_AUTH: `1`, `true`, `yes` or `on` opens
    it, and any other value closes it. Unrecognised fails closed, for the same
    reason it fails towards auth staying on.
    """
    explicit = env.get('ALFRED_ALLOW_REGISTRATION')
    if _given(explicit):
        return _truthy(explicit)
    return not env.get('ALFRED_PRODUCTION')


ALLOW_REGISTRATION = resolve_allow_registration(environ)


def resolve_dev_skip_auth(env):
    """Whether to accept unauthenticated requests as a fixed dev user.

    Refuses to combine with ALFRED_PRODUCTION. Raising here means a
    misconfigured production container fails to boot instead of coming up
    wide open, which is the only acceptable direction for this mistake --
    an unauthenticated API that starts successfully looks healthy.

    Takes the environment as an argument so this is testable without
    reimporting the module; the module-level value below is the real one.
    """
    requested = _truthy(env.get('ALFRED_DEV_SKIP_AUTH', ''))
    if not requested:
        return False
    if env.get('ALFRED_PRODUCTION'):
        raise RuntimeError(
            'ALFRED_DEV_SKIP_AUTH is set together with ALFRED_PRODUCTION. '
            'The auth bypass is a local development convenience and must '
            'never run in production. Refusing to start.'
        )
    return True


# Skips login entirely and treats every caller as a fixed local user. Off
# unless explicitly asked for. See docs/dev-auth.md.
DEV_SKIP_AUTH = resolve_dev_skip_auth(environ)

# The account the bypass acts as. A real, persisted user, so routes that
# attribute a render to `user.id` behave as they will with auth on.
#
# RFC 2606 reserved, so it cannot reach anyone if a code path ever mails it.
#
# It has to be reserved *and* valid, which narrows the field more than it
# looks. dev@localhost was the first attempt: the User document stored it, so
# every gated route worked, but UserRead types email as EmailStr and rejected
# it on the way out -- /users/me alone returned 500. dev@alfred.invalid was
# the second: `.invalid` is the RFC's own "guaranteed not to resolve" TLD, but
# pydantic's validator rejects reserved TLDs outright. RFC 2606 also reserves
# the second-level domains example.com/net/org, which do validate.
DEV_USER_EMAIL = environ.get('ALFRED_DEV_USER_EMAIL', 'dev@example.com')

DATA_DIR = environ.get('DATA_DIR', 'data')
# Where finished renders are written, and therefore where anything wanting to
# read one has to look. It was a bare 'videos' literal inside the Celery task,
# so nothing else could agree with it without repeating the string -- and the
# delivery endpoint duly looked in DATA_DIR instead and found nothing.
VIDEO_DIR = environ.get('VIDEO_DIR', 'videos')
STATIC_DIR = environ.get('STATIC_DIR', 'dist')

DB_URL = environ.get('DB_URL')
DB_NAME = environ.get('DB_NAME', 'db')

CELERY_BROKER = environ.get('CELERY_BROKER')
CELERY_BACKEND = environ.get('CELERY_BACKEND')

BUCKET_NAME = environ.get('ALFRED_BUCKET_NAME', 'tower-renders')
DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024  # 5MB

EMAIL_USERNAME = environ.get('EMAIL_USERNAME')
EMAIL_PASSWORD = environ.get('EMAIL_PASSWORD')
EMAIL_SERVER = environ.get('EMAIL_SERVER')
EMAIL_PORT = environ.get('EMAIL_PORT')
EMAIL_SENDTO = environ.get('EMAIL_SENDTO')
if EMAIL_SENDTO:
    EMAIL_SENDTO = EMAIL_SENDTO.split(',')

INVOICE_EMAIL_BODY = '''Please find attached an invoice for this week's renders. 

If you have any questions, feel free to contact us.

Thanks!

~Alfred
alfred.quaternion.media
'''


class CeleryConfig:
    task_serializer = "pickle"
    result_serializer = "pickle"
    event_serializer = "json"
    accept_content = ["application/json", "application/x-python-serialize"]
    result_accept_content = ["application/json", "application/x-python-serialize"]
