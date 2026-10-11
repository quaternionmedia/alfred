from email.message import EmailMessage
from mimetypes import guess_type
from smtplib import SMTP

from alfred.config import (
    EMAIL_PASSWORD,
    EMAIL_PORT,
    EMAIL_SERVER,
    EMAIL_USERNAME,
)


def sendMail(recepients, subject, message, attachments=None):
    # `attachments=None`, not `[]`. A list literal in a signature is created
    # once at import and shared by every call that omits the argument, so
    # anything appended to it leaks into the next mail sent.
    attachments = attachments or []
    try:
        msg = EmailMessage()
        msg.set_content(message)
        msg['From'] = EMAIL_USERNAME
        msg['To'] = recepients
        msg['Subject'] = subject
        if len(attachments):
            for path in attachments:
                ctype, encoding = guess_type(path)
                if ctype is None or encoding is not None:
                    # No guess could be made, or the file is encoded (compressed), so
                    # use a generic bag-of-bits type.
                    ctype = 'application/octet-stream'
                maintype, subtype = ctype.split('/', 1)
                with open(path, 'rb') as f:
                    msg.add_attachment(
                        f.read(), maintype=maintype, subtype=subtype, filename=path
                    )

        s = SMTP(EMAIL_SERVER, EMAIL_PORT)
        # s.set_debuglevel(1)
        s.starttls()
        s.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        s.send_message(msg)
        s.quit()
        return True
    except Exception as e:
        print('error sending email', e)
        return False
