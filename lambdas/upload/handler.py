import json
import os
import uuid

import boto3

from utils import build_response, get_timestamp
from constants import STATUS_PENDING

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

BUCKET_NAME = os.environ['BUCKET_NAME']
SUBMISSIONS_TABLE = os.environ['SUBMISSIONS_TABLE']

table = dynamodb.Table(SUBMISSIONS_TABLE)


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

        table.put_item(Item={
            'submissionId': submission_id,
            'userId': user_id,
            's3Key': s3_key,
            's3Bucket': BUCKET_NAME,
            'status': STATUS_PENDING,
            'uploadedAt': timestamp,
        })

        return build_response(200, {
            'submissionId': submission_id,
            'uploadUrl': upload_url,
        })

    except Exception as e:
        return build_response(500, {'error': str(e)})
