import json
import os

import boto3

from utils import get_timestamp
from constants import STATUS_ACCEPTED, STATUS_REJECTED

dynamodb = boto3.resource('dynamodb')
SUBMISSIONS_TABLE = os.environ['SUBMISSIONS_TABLE']
table = dynamodb.Table(SUBMISSIONS_TABLE)


def lambda_handler(event, context):
    submission_id = event.get('submissionId')

    if not submission_id and 'error-info' in event:
        submission_id = event.get('error-info', {}).get('submissionId')
    if not submission_id:
        for key in ('s3Key', 's3Bucket'):
            if key in event:
                continue

    final_decision = event.get('finalDecision', {})
    status = final_decision.get('status', STATUS_REJECTED)
    reason = final_decision.get('reason', 'unknown')

    if 'error-info' in event:
        err = event['error-info']
        status = STATUS_REJECTED
        reason = f"Pipeline error: {err.get('Error', 'Unknown')} - {err.get('Cause', 'Unknown')[:200]}"

    update_expr = 'SET #s = :status, completedAt = :ts, rejectionReason = :reason'
    expr_values = {
        ':status': status,
        ':ts': get_timestamp(),
        ':reason': reason if status == STATUS_REJECTED else None,
    }
    expr_names = {'#s': 'status'}

    if 'qualityCheckResult' in event:
        update_expr += ', qualityCheckResult = :qc'
        qc = event['qualityCheckResult'].copy()
        qc.pop('passed', None)
        expr_values[':qc'] = json.dumps(qc)

    if 'duplicationCheckResult' in event:
        update_expr += ', duplicationCheckResult = :dc'
        dc = event['duplicationCheckResult'].copy()
        dc.pop('embedding', None)
        dc.pop('passed', None)
        expr_values[':dc'] = json.dumps(dc)

    if 'customCheckResult' in event:
        update_expr += ', customCheckResult = :cc'
        cc = event['customCheckResult'].copy()
        cc.pop('passed', None)
        expr_values[':cc'] = json.dumps(cc)

    table.update_item(
        Key={'submissionId': submission_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )

    return {
        'submissionId': submission_id,
        'status': status,
        'reason': reason,
    }
