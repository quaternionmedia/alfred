from pdfrw import PdfReader, PdfWriter, PageMerge
from io import BytesIO
from reportlab.pdfgen import canvas

left = 200
top = 600
lineHeight = 20
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

def generate_invoice(renders):
    data = BytesIO()
    pdf = canvas.Canvas(data)
    pdf.setFont("Helvetica", 16)
    
    for i, render in enumerate(renders):
        pdf.drawString(x=left, y=top+lineHeight*i, text=render['filename'])
    
    pdf.save()
    data.seek(0)
    
    final = watermarker('QM - Invoice template.pdf', data)
    
    save(final, 'alfred invoice.pdf')

