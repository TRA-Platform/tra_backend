import markdown
import pdfkit
import tempfile
import os
from django.conf import settings

def convert_md_to_html(md_content):
    html = markdown.markdown(
        md_content,
        extensions=['tables', 'fenced_code', 'codehilite']
    )
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Software Requirements Specification</title>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 40px; }}
            h1, h2, h3, h4, h5, h6 {{ color: #2c3e50; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f5f5f5; }}
            code {{ background-color: #f8f8f8; padding: 2px 4px; border-radius: 3px; }}
            pre {{ background-color: #f8f8f8; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        {html}
    </body>
    </html>
    """

def convert_md_to_pdf(md_content):
    html_content = convert_md_to_html(md_content)
    
    with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as temp_html:
        temp_html.write(html_content.encode('utf-8'))
        temp_html_path = temp_html.name

    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
        temp_pdf_path = temp_pdf.name

    try:
        pdfkit.from_file(
            temp_html_path,
            temp_pdf_path,
            options={
                'page-size': 'A4',
                'margin-top': '20mm',
                'margin-right': '20mm',
                'margin-bottom': '20mm',
                'margin-left': '20mm',
                'encoding': 'UTF-8',
                'no-outline': None
            }
        )
        
        with open(temp_pdf_path, 'rb') as pdf_file:
            pdf_content = pdf_file.read()
            
        return pdf_content
    finally:
        os.unlink(temp_html_path)
        os.unlink(temp_pdf_path) 