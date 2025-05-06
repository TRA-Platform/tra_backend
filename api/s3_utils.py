import boto3
import os
from django.conf import settings
from datetime import datetime

def get_s3_client():
    session = boto3.session.Session()
    return session.client(
        service_name='s3',
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION
    )

def get_content_type(file_extension):
    content_types = {
        'md': 'text/markdown; charset=utf-8',
        'html': 'text/html; charset=utf-8',
        'pdf': 'application/pdf'
    }
    return content_types.get(file_extension, 'application/octet-stream')

def upload_to_s3(content, filename, bucket_name, file_extension='md'):
    s3_client = get_s3_client()
    content_type = get_content_type(file_extension)
    
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=filename,
            Body=content,
            ContentType=content_type,
            ACL='public-read',
        )
        
        url = f"{settings.S3_UPLOAD_URL}/{filename}"
        return url
    except Exception as e:
        raise Exception(f"Failed to upload to S3: {str(e)}")

def generate_export_filename(project_name, export_id, file_extension='md'):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_project_name = ''.join(c for c in project_name if c.isalnum() or c in (' ', '-', '_')).strip()
    safe_project_name = safe_project_name.replace(' ', '_')
    return f"exports/{safe_project_name}_{export_id}_{timestamp}.{file_extension}"