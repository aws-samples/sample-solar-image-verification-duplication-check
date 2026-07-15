import json
import os
import uuid

import boto3
from botocore.config import Config

from utils import build_response, get_timestamp
from constants import STATUS_PENDING
from db import get_connection

# Regional endpoint + SigV4 so presigned URLs point at s3.<region>.amazonaws.com
# directly. The global endpoint 307-redirects for newly created buckets, which
# breaks the signature for clients that follow the redirect.
s3 = boto3.client(
    's3',
    region_name=os.environ.get('AWS_REGION', 'ap-south-1'),
    config=Config(signature_version='s3v4', s3={'addressing_style': 'virtual'}),
    endpoint_url=f"https://s3.{os.environ.get('AWS_REGION', 'ap-south-1')}.amazonaws.com",
)

BUCKET_NAME = os.environ['BUCKET_NAME']


def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        user_id = body.get('userId', 'anonymous')
        file_name = body.get('fileName', 'image.jpg')
        content_type = body.get('contentType', 'image/jpeg')

        submission_id = str(uuid.uuid4())
        safe_name = file_name.replace(' ', '_').replace('(', '').replace(')', '')
        s3_key = f"uploads/{submission_id}/{safe_name}"
        timestamp = get_timestamp()

        upload_url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': s3_key,
                'ContentType': content_type,
            },
            ExpiresIn=300,
        )

        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO submissions
                    (submission_id, user_id, s3_key, s3_bucket, status, uploaded_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (submission_id, user_id, s3_key, BUCKET_NAME, STATUS_PENDING, timestamp),
            )

        return build_response(200, {
            'submissionId': submission_id,
            'uploadUrl': upload_url,
        })

    except Exception as e:
        return build_response(500, {'error': str(e)})
