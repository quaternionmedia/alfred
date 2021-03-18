from fastapi import APIRouter, Body
from smtplib import SMTP
from email.message import EmailMessage
from config import EMAIL_PORT, EMAIL_SERVER, EMAIL_USERNAME, EMAIL_PASSWORD, EMAIL_SENDTO, INVOICE_EMAIL_BODY

def sendMail(recepients, subject, message, attachments=None):
    try:
        msg = EmailMessage()
        msg.set_content(message)
        msg['From'] = EMAIL_USERNAME
        msg['To'] = recepients
        msg['Subject'] = subject
        s=SMTP(config.EMAIL_SERVER, config.EMAIL_PORT)
        s.set_debuglevel(1)
        s.starttls()
        s.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        s.send_message(msg)
        s.quit()
        return True
    except Exception as e:
        print('error sending email', e)
        return False

emailAPI = APIRouter()

@emailAPI.post('/report')
async def reportIssue(name: str, issue: str = Body(...)):
    if not sendMail(issue, name):
        print('error reporting issue with ', name, issue)
        raise HTTPException(status_code=500, detail='error sending email')
