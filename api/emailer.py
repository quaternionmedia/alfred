from smtplib import SMTP
from email.message import EmailMessage
import config

def sendMail(message, subject):
    try:
        msg = EmailMessage()
        msg.set_content(message)
        msg['Subject'] = subject
        msg['From'] = config.EMAIL_USERNAME
        msg['To'] = config.EMAIL_SENDTO
        s=SMTP(config.EMAIL_SERVER, config.EMAIL_PORT)
        s.set_debuglevel(1)
        s.starttls()
        s.login(config.EMAIL_USERNAME, config.EMAIL_PASSWORD)
        s.send_message(msg)
        s.quit()
        return True
    except Exception as e:
        print('error sending email', e)
        return False