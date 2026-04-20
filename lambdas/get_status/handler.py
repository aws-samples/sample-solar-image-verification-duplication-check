import json
import os
from datetime import datetime, timezone, timedelta

import boto3

from utils import build_response, get_timestamp

dynamodb = boto3.resource('dynamodb')
SUBMISSIONS_TABLE = os.environ['SUBMISSIONS_TABLE']
table = dynamodb.Table(SUBMISSIONS_TABLE)

STALE_THRESHOLD_MINUTES = 5


def auto_expire_stale(item: dict) -> dict:
    status = item.get('status', '')
    if status not in ('PENDING', 'PROCESSING'):
        return item

    uploaded = item.get('uploadedAt', '')
    if not uploaded:
        return item

    try:
        upload_time = datetime.fromisoformat(uploaded)
        now = datetime.now(timezone.utc)
        if (now - upload_time) > timedelta(minutes=STALE_THRESHOLD_MINUTES):
            table.update_item(
                Key={'submissionId': item['submissionId']},
                UpdateExpression='SET #s = :s, rejectionReason = :r, completedAt = :c',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={
                    ':s': 'REJECTED',
                    ':r': 'Pipeline timed out - verification did not complete within 5 minutes',
                    ':c': get_timestamp(),
                },
            )
            item['status'] = 'REJECTED'
            item['rejectionReason'] = 'Pipeline timed out - verification did not complete within 5 minutes'
            item['completedAt'] = get_timestamp()
    except (ValueError, TypeError):
        pass

    return item


def format_submission(item: dict) -> dict:
    item = auto_expire_stale(item)
    result = {
        'submissionId': item['submissionId'],
        'userId': item.get('userId', ''),
        'status': item.get('status', 'UNKNOWN'),
        'uploadedAt': item.get('uploadedAt', ''),
        'completedAt': item.get('completedAt'),
        'rejectionReason': item.get('rejectionReason'),
    }
    for key in ('qualityCheckResult', 'duplicationCheckResult', 'customCheckResult'):
        if key in item:
            try:
                result[key] = json.loads(item[key]) if isinstance(item[key], str) else item[key]
            except (json.JSONDecodeError, TypeError):
                result[key] = item[key]
    return result


def lambda_handler(event, context):
    path_params = event.get('pathParameters') or {}
    query_params = event.get('queryStringParameters') or {}

    submission_id = path_params.get('submissionId')
    if submission_id:
        response = table.get_item(Key={'submissionId': submission_id})
        item = response.get('Item')
        if not item:
            return build_response(404, {'error': 'Submission not found'})
        return build_response(200, format_submission(item))

    user_id = query_params.get('userId')
    if user_id:
        response = table.query(
            IndexName='userId-index',
            KeyConditionExpression='userId = :uid',
            ExpressionAttributeValues={':uid': user_id},
            ScanIndexForward=False,
        )
        items = [format_submission(i) for i in response.get('Items', [])]
        return build_response(200, items)

    return build_response(400, {'error': 'Provide submissionId or userId'})
