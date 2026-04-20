import json
import os

import boto3

from utils import build_response

s3 = boto3.client('s3')
sfn = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')

SUBMISSIONS_TABLE = os.environ['SUBMISSIONS_TABLE']
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']

table = dynamodb.Table(SUBMISSIONS_TABLE)


def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        submission_id = body.get('submissionId')

        if not submission_id:
            return build_response(400, {'error': 'submissionId is required'})

        item = table.get_item(Key={'submissionId': submission_id}).get('Item')
        if not item:
            return build_response(404, {'error': 'Submission not found'})

        s3_bucket = item['s3Bucket']
        s3_key = item['s3Key']

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
