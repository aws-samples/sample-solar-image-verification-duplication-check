import json
import os

import boto3

from utils import build_response
from constants import PAYMENT_VALIDATING

s3 = boto3.client('s3')
sfn = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')

SUBMISSIONS_TABLE = os.environ['SUBMISSIONS_TABLE']
CHEQUE_STATE_MACHINE_ARN = os.environ['CHEQUE_STATE_MACHINE_ARN']

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
        cheque_key = item.get('chequeS3Key')
        if not cheque_key:
            return build_response(400, {'error': 'No cheque uploaded for this submission'})

        s3.head_object(Bucket=s3_bucket, Key=cheque_key)

        table.update_item(
            Key={'submissionId': submission_id},
            UpdateExpression='SET paymentStatus = :p',
            ExpressionAttributeValues={':p': PAYMENT_VALIDATING},
        )

        sfn.start_execution(
            stateMachineArn=CHEQUE_STATE_MACHINE_ARN,
            name=f"cheque-{submission_id}",
            input=json.dumps({
                'submissionId': submission_id,
                's3Bucket': s3_bucket,
                'chequeS3Key': cheque_key,
                'expectedHolderName': item.get('expectedHolderName', ''),
            }),
        )

        return build_response(200, {'submissionId': submission_id, 'paymentStatus': PAYMENT_VALIDATING})

    except s3.exceptions.ClientError:
        return build_response(400, {'error': 'Cheque file not found in S3. Upload may not be complete.'})
    except Exception as e:
        return build_response(500, {'error': str(e)})
