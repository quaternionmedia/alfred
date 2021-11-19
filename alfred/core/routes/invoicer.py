from pdfrw import PdfReader, PdfWriter, PageMerge
from io import BytesIO
from reportlab.pdfgen import canvas
from ..utils.db import get_sync_db
from bson.objectid import ObjectId
from math import ceil
from datetime import datetime

left = 55
top = 557
right = 512
lineHeight = 16.2
bottom = 88
unitPrice = 25
weeklyMax = 150

lines = 25

def watermarker(path, watermark):
    base_pdf = PdfReader(path)
    watermark_pdf = PdfReader(watermark)
    mark = watermark_pdf.pages[0]

    for page in range(len(base_pdf.pages)):
        merger = PageMerge(base_pdf.pages[page])
        merger.add(mark).render()
    result = BytesIO()
    PdfWriter().write(result, base_pdf)
    result.seek(0)
    return result

def save(form: BytesIO, filename: str):
    with open(filename, 'wb') as f:
        f.write(form.read())

def generate_invoice(username, startDate, endDate):
    total = 0
    q = {'username': username, '_id': {'$gt': ObjectId.from_datetime(startDate), '$lt': ObjectId.from_datetime(endDate)}}
    db = get_db()
    renders = list(db.deleted.find(q))
    renders += list(db.renders.find(q))
    results = []
    date = datetime.today()
    invoiceNumber = f'{date.year}{date.month:02d}{date.day:02d}'
    for page in range(ceil(len(renders)/ lines) or 1):
        data = BytesIO()
        pdf = canvas.Canvas(data)
        pdf.setFont("Helvetica", 9)
        pdf = setDate(pdf)
        pdf = setBillTo(pdf, username)
        pdf = setInvoiceNumber(pdf, invoiceNumber, page=page if len(renders) > lines else None)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(x=left, y=top, text=f'Alfred - Renders from {startDate.isoformat().split("T")[0]} to {endDate.isoformat().split("T")[0]}')
        pdf.setFont("Helvetica", 10)
        for i, render in enumerate(renders[page*lines:(page+1)*lines]):
            pdf.drawString(x=left, y=top-lineHeight*(i+1), text=render['filename'])
            if total < weeklyMax:
                total += unitPrice
                pdf.drawString(x=right, y=top-lineHeight*(i+1), text=f'$ {unitPrice:.2f}')
        # draw subtotal
        pdf.drawString(x=right, y=bottom+lineHeight*2.4, text=f'$ {total:.2f}')
        if page == len(renders)//lines:
            # draw total
            pdf.drawString(x=right, y=bottom, text=f'$ {total:.2f}')
        
        pdf.save()
        data.seek(0)
        final = watermarker('QM - Invoice template.pdf', data)
        filename = f'{invoiceNumber}_alfred invoice_{page}.pdf'
        save(final, filename)
        results.append(filename)
    return results

def setDate(pdf):
    t = datetime.today().isoformat()
    date = t[:t.index('T')]
    pdf.drawString(x=right, y=top+92, text=date)
    return pdf

def setBillTo(pdf, username):
    db = get_sync_db()
    user = db.users.find_one({'username': username})
    for i, line in enumerate(user['address']):
        pdf.drawString(x=left, y=top+78-i*12, text = line)
    return pdf
    
def setInvoiceNumber(pdf, invoiceNumber, page=None):
    pdf.drawString(x=right, y=top+78, text=invoiceNumber + ('-' + str(page) if page is not None else ''))
    return pdf
