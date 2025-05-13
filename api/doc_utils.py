import markdown
import tempfile
import subprocess
import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

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
    
    output_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False).name
    
    try:
        cmd = [
            'wkhtmltopdf',
            '--enable-javascript',
            '--javascript-delay', '1000',
            '--image-quality', '90',
            '--margin-top', '20',
            '--margin-right', '20',
            '--margin-bottom', '20',
            '--margin-left', '20',
            temp_html_path,
            output_pdf
        ]
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"wkhtmltopdf error: {stderr.decode('utf-8')}")
            raise Exception(f"wkhtmltopdf failed with error code {process.returncode}")
        
        with open(output_pdf, 'rb') as f:
            pdf_data = f.read()
            
        return pdf_data
    
    except Exception as e:
        logger.error(f"Error converting to PDF: {str(e)}")
        raise
    
    finally:
        if os.path.exists(temp_html_path):
            os.unlink(temp_html_path)
        if os.path.exists(output_pdf):
            os.unlink(output_pdf) 