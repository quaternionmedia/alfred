from datetime import date, datetime, time, timezone

from fastapi import APIRouter
from fastapi.exceptions import HTTPException

from alfred.config import EMAIL_SENDTO, INVOICE_EMAIL_BODY

from ..utils import sendMail
from .invoicer import generate_invoice

adminAPI = APIRouter()


@adminAPI.post('/invoice')
async def sendInvoice(client: str, startDate: date, endDate: date):
    """# Send Invoice
    Generates a PDF invoice and sends an email to the client
    for all renders executed in the specified period
    """
    midnight = time(0)
    startDate = datetime.combine(startDate, midnight, timezone.utc)
    endDate = datetime.combine(endDate, midnight, timezone.utc)
    invoices = generate_invoice(client, startDate, endDate)
    body = INVOICE_EMAIL_BODY
    if not sendMail(
        recepients=EMAIL_SENDTO,
        subject='alfred invoice',
        message=body,
        attachments=invoices,
    ):
        print('error sending  ', EMAIL_SENDTO, body)
        raise HTTPException(status_code=500, detail='error sending email')
