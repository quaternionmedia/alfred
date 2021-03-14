from pdfrw import PdfReader, PdfWriter, PageMerge
from io import BytesIO
from reportlab.pdfgen import canvas
from db import db
from math import ceil
from datetime import datetime
clientAddress = ['46 Mile', '901 Mission Street', 'San Francisco, CA 94103', 'info@46mile.com']
left = 55
top = 557
right = 512
lineHeight = 16.2
bottom = 88
unitPrice = 25

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

def generate_invoice(username):
    total = 0
    renders = list(db.deleted.find({'user': username}))
    renders += list(db.renders.find({'user': username}))
    for page in range(ceil(len(renders)/ lines)):
        data = BytesIO()
        pdf = canvas.Canvas(data)
        pdf.drawString(x=left, y=top, text='Alfred - renders')
        pdf.setFont("Helvetica", 10)
        for i, render in enumerate(renders[page*lines:(page+1)*lines]):
            pdf.drawString(x=left, y=top-lineHeight*(i+1), text=render['filename'])
            if total < 100:
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
        save(final, f'alfred invoice-{page}.pdf')

