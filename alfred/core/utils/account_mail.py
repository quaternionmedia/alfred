"""Account tokens, delivered: password resets and address confirmations.

fastapi-users issues a single-use token and hands it to a hook. The hook
printed it, and nothing else ever saw it -- so outside development, where
nobody asking for a reset can read the server's log, a reset could be asked
for and never finished. When mail is configured the token now goes to the
account's own address, as a link into the app's account page
(`/#!/account/<reset|verify>?token=...`).

**Configured** means the existing mail settings, EMAIL_SERVER and
EMAIL_USERNAME (`utils.email.sendMail` sends it), and ALFRED_PUBLIC_URL, which
the link is built on -- never the request's Host header; see
`config.resolve_public_url`.

**Off the request.** Mail goes out from one background thread, so asking for a
reset answers at once whether the mail server is quick, slow or down, and
answers alike for an address with an account and one without. A send that
fails is logged by `sendMail`, without the message.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from urllib.parse import quote

from alfred import config

from .email import sendMail

RESET = 'reset'
VERIFY = 'verify'

# How long one attempt to reach the mail server may take, in seconds. Mail is
# sent one message at a time, so a server that never answers would otherwise
# hold up every message after it.
SEND_TIMEOUT = 20


@dataclass(frozen=True)
class Message:
    subject: str
    body: str


MESSAGES = {
    RESET: Message(
        subject='Reset your Alfred password',
        body=(
            'Somebody asked to reset the password of the Alfred account for '
            'this address. To choose a new one, open this link within '
            '{lifetime}:\n\n{link}\n\nIf it was not you, ignore this message: '
            'the password stays as it is.\n'
        ),
    ),
    VERIFY: Message(
        subject='Confirm your address for Alfred',
        body=(
            'To confirm that this address belongs to your Alfred account, open '
            'this link within {lifetime}:\n\n{link}\n\nIf you did not ask for '
            'this, ignore this message.\n'
        ),
    ),
}

_outbox = ThreadPoolExecutor(max_workers=1, thread_name_prefix='account-mail')


def configured() -> bool:
    """Whether account mail can be sent: a mail server, and an app to link to."""
    return bool(config.EMAIL_SERVER and config.EMAIL_USERNAME and config.PUBLIC_URL)


def link(purpose, token) -> str:
    """The account page that finishes `purpose` with `token`."""
    return f'{config.PUBLIC_URL}/#!/account/{purpose}?token={quote(token, safe="")}'


def lifetime(seconds) -> str:
    """'an hour', '2 hours', '30 minutes': how long a token works, in words."""
    if seconds % 3600 == 0:
        hours = seconds // 3600
        return 'an hour' if hours == 1 else f'{hours} hours'
    return f'{round(seconds / 60)} minutes'


def compose(purpose, token, lifetime_seconds) -> Message:
    """The mail carrying `token`: its subject and its plain-text body."""
    message = MESSAGES[purpose]
    body = message.body.format(
        link=link(purpose, token), lifetime=lifetime(lifetime_seconds)
    )
    return Message(subject=message.subject, body=body)


def dispatch(send):
    """Run `send` on the mail thread. Tests replace this to send inline."""
    _outbox.submit(send)


def deliver(purpose, address, token, lifetime_seconds) -> bool:
    """Mail `token` to `address`, in the background.

    Whether a message was queued: False, with nothing sent, unless account
    mail is configured.
    """
    if not configured():
        return False
    message = compose(purpose, token, lifetime_seconds)
    dispatch(
        partial(sendMail, address, message.subject, message.body, timeout=SEND_TIMEOUT)
    )
    return True
