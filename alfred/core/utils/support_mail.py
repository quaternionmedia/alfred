"""Mail to support, handed to the worker to send (`tasks.mailSupport`).

`POST /render/{id}/report` and `POST /invoice` sent their mail over SMTP from
the request, in a thread with no timeout: a mail server that was slow held the
request, and one that never answered held it, and a thread of the api's pool,
for as long as the connection lasted. They queue the mail now and answer 202
as soon as it is queued. The worker sends it within ALFRED_SMTP_TIMEOUT, and
tries again later when the failure may pass.

What is queued is the mail's subject, its text and any attachments, and a few
words naming it for the log. Not the addresses: the worker sends to
EMAIL_SENDTO itself.
"""

from base64 import b64encode
from typing import Literal, Optional

from pydantic import BaseModel

from ..errors import Code, Refusal
from .email import support_mail_configured
from .tasks import mailSupport


class MailQueued(BaseModel):
    """The answer to a request whose mail was queued (202)."""

    state: Literal['queued']
    # The worker's id for the job, which its log names; null if the queue
    # gave none.
    job: Optional[str] = None


def get_mail_queue():
    """How mail reaches the worker: Celery's `delay`.

    A dependency so that a test can record what would be sent instead.
    """
    return mailSupport.delay


NOT_CONFIGURED = (
    'This server has no mail set up (EMAIL_SERVER, EMAIL_USERNAME and '
    'EMAIL_SENDTO), so nothing can be mailed.'
)


def refuse_unless_configured():
    """503 when there is no mail to send with (`mail_not_configured`):
    checked before anything is made or queued, so the caller hears it now
    rather than never."""
    if not support_mail_configured():
        raise Refusal(Code.MAIL_NOT_CONFIGURED, NOT_CONFIGURED)


def attachment(filename, data: bytes) -> dict:
    """A file as the queue carries it: JSON, so its bytes in base64 (C7)."""
    return {'filename': filename, 'content': b64encode(data).decode('ascii')}


def queue_mail(queue, about, subject, message, attachments=()) -> MailQueued:
    """Queue a mail to support; 503 if the broker would not take it
    (`mail_not_queued`).

    Blocking: a send to the broker. `about` names the mail in the worker's
    log, and must hold nothing a mail does -- no address, no text.
    """
    try:
        job = queue(
            about=about,
            subject=subject,
            message=message,
            attachments=list(attachments),
        )
    except Exception as exc:  # noqa: BLE001 - the broker is down, or worse
        # The kind only: a serializer's complaint can quote what it was given.
        print(f'could not queue the mail about {about}:', type(exc).__name__)
        raise Refusal(
            Code.MAIL_NOT_QUEUED, 'The mail could not be queued; try again later.'
        ) from exc
    return MailQueued(state='queued', job=getattr(job, 'id', None))
