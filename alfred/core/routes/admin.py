from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends

from alfred.config import INVOICE_EMAIL_BODY

from ..utils.support_mail import (
    MailQueued,
    attachment,
    get_mail_queue,
    queue_mail,
    refuse_unless_configured,
)
from .invoicer import generate_invoice

adminAPI = APIRouter()


# A plain function, not a coroutine: FastAPI runs it in its thread pool. The
# invoice reads renders with the synchronous database client and draws and
# writes PDFs, and the queue send is a round trip to the broker; as a
# coroutine each step held the event loop.
@adminAPI.post(
    '/invoice',
    status_code=202,
    response_model=MailQueued,
    responses={
        503: {'description': 'no mail set up on this server, or the queue is down'}
    },
)
def sendInvoice(
    client: str, startDate: date, endDate: date, queue=Depends(get_mail_queue)
):
    """# Send Invoice
    Generates a PDF invoice for all renders executed in the specified period,
    and mails it to the support team (EMAIL_SENDTO).

    Answers 202 once the mail is queued, with the worker's `job` id; the
    worker sends it, and tries again for a while if the mail server is down.
    503 when the server has no mail set up (`mail_not_configured`), or the
    queue will not take it (`mail_not_queued`).
    """
    refuse_unless_configured()
    midnight = time(0)
    startDate = datetime.combine(startDate, midnight, timezone.utc)
    endDate = datetime.combine(endDate, midnight, timezone.utc)
    invoices = generate_invoice(client, startDate, endDate)
    # The PDFs travel with the job: the worker cannot see the files the api
    # wrote. Queued, not sent from here, where a mail server that never
    # answered held this request for as long as the connection lasted.
    files = []
    for path in invoices:
        with open(path, 'rb') as handle:
            files.append(attachment(path, handle.read()))
    return queue_mail(
        queue,
        about='an invoice',
        subject='alfred invoice',
        message=INVOICE_EMAIL_BODY,
        attachments=files,
    )
