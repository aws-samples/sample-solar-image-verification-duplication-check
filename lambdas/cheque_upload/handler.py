import json
import os

import boto3

from utils import build_response, get_timestamp
from constants import STATUS_ACCEPTED, PAYMENT_PENDING_CHEQUE

s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

BUCKET_NAME = os.environ['BUCKET_NAME']
SUBMISSIONS_TABLE = os.environ['SUBMISSIONS_TABLE']

table = dynamodb.Table(SUBMISSIONS_TABLE)


def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        submission_id = body.get('submissionId')
        file_name = body.get('fileName', 'cheque.jpg')
        content_type = body.get('contentType', 'image/jpeg')
        expected_holder_name = (body.get('expectedHolderName') or '').strip()

        if not submission_id:
            return build_response(400, {'error': 'submissionId is required'})
        if not expected_holder_name:
            return build_response(400, {'error': 'expectedHolderName is required'})

        item = table.get_item(Key={'submissionId': submission_id}).get('Item')
        if not item:
            return build_response(404, {'error': 'Submission not found'})
        if item.get('status') != STATUS_ACCEPTED:
            return build_response(400, {
                'error': f"Submission is not ACCEPTED (current status: {item.get('status')})",
            })

        safe_name = file_name.replace(' ', '_').replace('(', '').replace(')', '')
        s3_key = f"cheques/{submission_id}/{safe_name}"

        upload_url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': s3_key,
                'ContentType': content_type,
            },
            ExpiresIn=300,
        )

        table.update_item(
            Key={'submissionId': submission_id},
            UpdateExpression='SET chequeS3Key = :k, expectedHolderName = :n, paymentStatus = :p, chequeUploadedAt = :t',
            ExpressionAttributeValues={
                ':k': s3_key,
                ':n': expected_holder_name,
                ':p': PAYMENT_PENDING_CHEQUE,
                ':t': get_timestamp(),
            },
        )

        return build_response(200, {
            'submissionId': submission_id,
            'uploadUrl': upload_url,
            'chequeS3Key': s3_key,
        })

    except Exception as e:
        return build_response(500, {'error': str(e)})
