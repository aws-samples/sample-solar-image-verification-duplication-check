import json
import os

import boto3

from utils import build_response
from db import get_connection

s3 = boto3.client('s3')
sfn = boto3.client('stepfunctions')

STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']


def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        submission_id = body.get('submissionId')

        if not submission_id:
            return build_response(400, {'error': 'submissionId is required'})

        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                'SELECT s3_bucket, s3_key FROM submissions WHERE submission_id = %s',
                (submission_id,),
            )
            row = cur.fetchone()

        if not row:
            return build_response(404, {'error': 'Submission not found'})

        s3_bucket, s3_key = row

        s3.head_object(Bucket=s3_bucket, Key=s3_key)

        sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=submission_id,
            input=json.dumps({
                'submissionId': submission_id,
                's3Bucket': s3_bucket,
                's3Key': s3_key,
            }),
        )

        return build_response(200, {'submissionId': submission_id, 'status': 'PROCESSING'})

    except s3.exceptions.ClientError:
        return build_response(400, {'error': 'File not found in S3. Upload may not be complete.'})
    except Exception as e:
        return build_response(500, {'error': str(e)})
