from pdfrw import PdfReader, PdfWriter, PageMerge
from io import BytesIO
from reportlab.pdfgen import canvas
from db import db
from math import ceil

left = 60
top = 557
right = 520
lineHeight = 16.2
bottom = 88
unitPrice = 25

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

def generate_invoice():
    total = 0
    renders = list(db.renders.find())
    for page in range(ceil(len(renders)/ 26)):
        data = BytesIO()
        pdf = canvas.Canvas(data)
        pdf.setFont("Helvetica", 10)
        for i, render in enumerate(renders[page*26:(page+1)*26]):
            pdf.drawString(x=left, y=top-lineHeight*i, text=render['filename'])
            if total < 100:
                total += unitPrice
                pdf.drawString(x=right, y=top-lineHeight*i, text=f'$ {unitPrice:.2f}')
            # else:
            #     pdf.drawString(x=right, y=top-lineHeight*i, text='$ 0.00')
        if page != len(renders)//26:
            pdf.drawString(x=right, y=bottom+lineHeight*2.4, text=f'$ {total:.2f}')
        else:
            pdf.drawString(x=right, y=bottom, text=f'$ {total:.2f}')
        
        
        pdf.save()
        data.seek(0)
        final = watermarker('QM - Invoice template.pdf', data)
        save(final, f'alfred invoice-{page}.pdf')

