from fastapi import APIRouter
from datetime import datetime, date, time
from ..utils import sendMail
from .invoicer import generate_invoice

adminAPI = APIRouter()

@adminAPI.post('/invoice')
async def sendInvoice(client: str, startDate: date, endDate: date):
    """# Send Invoice
    Generates a PDF invoice and sends an email to the client for all renders executed in the specified period"""
    midnight = time(0)
    startDate = datetime.combine(startDate, midnight, UTC)
    endDate = datetime.combine(endDate, midnight, UTC)
    invoices = generate_invoice(client, startDate, endDate)
    body=INVOICE_EMAIL_BODY
    if not sendMail(recepients=EMAIL_SENDTO, subject=f'alfred invoice', message=body, attachments=invoices):
        print('error sending  ', name, issue)
        raise HTTPException(status_code=500, detail='error sending email')
