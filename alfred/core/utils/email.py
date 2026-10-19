"""Mail, over SMTP.

`send_mail` sends one message or raises. `sendMail` is the same as a yes or
no, for account mail, which sends from its own thread and only logs a failure.
Mail to support -- an issue with a render, an invoice -- goes through the
worker's queue instead (`tasks.mailSupport`), which tries again when a failure
may pass.

A failure is logged as `mail_failure` puts it: what kind of failure, and the
mail server's reply code, never the message, its subject or an address.
smtplib's own exceptions carry addresses -- a refused recipient is reported as
`{address: (code, reply)}`, and a reply can quote the address it refuses -- so
they are not printed as they are.
"""

from email.message import EmailMessage
from mimetypes import guess_type
from smtplib import (
    SMTP,
    SMTPException,
    SMTPRecipientsRefused,
    SMTPResponseException,
    SMTPServerDisconnected,
)

from alfred.config import (
    EMAIL_PASSWORD,
    EMAIL_PORT,
    EMAIL_SENDTO,
    EMAIL_SERVER,
    EMAIL_USERNAME,
)


class MailNotConfigured(Exception):
    """No mail server, or nobody to send to."""


def support_mail_configured() -> bool:
    """Whether mail to support can be sent: a server, a sender and recipients
    (EMAIL_SERVER, EMAIL_USERNAME and EMAIL_SENDTO, from the `.email` file)."""
    return bool(EMAIL_SERVER and EMAIL_USERNAME and EMAIL_SENDTO)


def compose(recipients, subject, message, attachments=()) -> EmailMessage:
    """A plain-text message, with `attachments` as `(filename, bytes)` pairs."""
    msg = EmailMessage()
    msg.set_content(message)
    msg['From'] = EMAIL_USERNAME
    msg['To'] = recipients
    msg['Subject'] = subject
    for filename, data in attachments:
        ctype, encoding = guess_type(filename)
        if ctype is None or encoding is not None:
            # No guess could be made, or the file is encoded (compressed), so
            # use a generic bag-of-bits type.
            ctype = 'application/octet-stream'
        maintype, subtype = ctype.split('/', 1)
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return msg


def send_mail(recipients, subject, message, attachments=(), timeout=None):
    """Send one message, or raise why not.

    `timeout` bounds each network operation, in seconds, for a caller that
    must not wait on a mail server indefinitely; left out, smtplib waits.
    """
    if not (EMAIL_SERVER and recipients):
        raise MailNotConfigured('no mail server, or no recipients, is configured')
    msg = compose(recipients, subject, message, attachments)
    s = SMTP(EMAIL_SERVER, EMAIL_PORT, **({'timeout': timeout} if timeout else {}))
    try:
        s.starttls()
        s.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        s.send_message(msg)
    except BaseException:
        # Closed, not quit: a server that has stopped answering would hold
        # QUIT for another timeout.
        s.close()
        raise
    try:
        s.quit()
    except Exception:  # noqa: BLE001 - sent; a goodbye that fails changes nothing
        # Not raised: the mail went, and a caller that tries again on failure
        # would send it twice.
        s.close()


def mail_failure(exc) -> str:
    """Why a send failed, as one line with no message and no address in it."""
    kind = type(exc).__name__
    if isinstance(exc, SMTPRecipientsRefused):
        codes = sorted({code for code, _ in exc.recipients.values()})
        return f'{kind}: every recipient was refused ({", ".join(map(str, codes))})'
    if isinstance(exc, SMTPResponseException):
        # The reply's text can quote an address; its code cannot.
        return f'{kind}: the mail server answered {exc.smtp_code}'
    if isinstance(exc, (SMTPException, MailNotConfigured)):
        # smtplib's own sentences and this module's, which name no address:
        # "Connection unexpectedly closed", "STARTTLS extension not supported
        # by server."
        return f'{kind}: {exc}'
    if isinstance(exc, TimeoutError):
        return f'{kind}: the mail server did not answer in time'
    if isinstance(exc, OSError) and exc.strerror:
        # "Connection refused", "Name or service not known".
        return f'{kind}: {exc.strerror}'
    return kind


def transient(exc) -> bool:
    """Whether a send that failed this way may pass if tried again later.

    A mail server that could not be reached, did not answer, or hung up, and
    any reply in the 400s, which SMTP keeps for "not now". Not a refusal in
    the 500s -- a login turned down, a recipient that does not exist -- nor
    what smtplib raises for a server lacking something, nor mail that is not
    configured: those fail the same way every time.
    """
    if isinstance(exc, SMTPRecipientsRefused):
        return all(400 <= code < 500 for code, _ in exc.recipients.values())
    if isinstance(exc, SMTPResponseException):
        return 400 <= exc.smtp_code < 500
    if isinstance(exc, SMTPServerDisconnected):
        return True
    if isinstance(exc, SMTPException):
        return False
    # The network: refused, unreachable, unresolved, timed out.
    return isinstance(exc, OSError)


def sendMail(recepients, subject, message, attachments=None, timeout=None):
    """`send_mail`, as True when sent and False, logged, when not.

    `attachments` are paths here, each attached under the name it is given.
    `attachments=None`, not `[]`: a list literal in a signature is created once
    at import and shared by every call that omits the argument, so anything
    appended to it would leak into the next mail sent.
    """
    try:
        files = []
        for path in attachments or []:
            with open(path, 'rb') as f:
                files.append((path, f.read()))
        send_mail(recepients, subject, message, files, timeout=timeout)
        return True
    except Exception as e:  # noqa: BLE001 - every failure is reported the same way
        print('error sending email:', mail_failure(e), flush=True)
        return False
