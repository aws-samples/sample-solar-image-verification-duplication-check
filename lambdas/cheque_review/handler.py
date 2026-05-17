import json
import os

import boto3

from utils import build_response, get_timestamp
from constants import PAYMENT_APPROVED, PAYMENT_DECLINED, PAYMENT_NEEDS_REVIEW

dynamodb = boto3.resource('dynamodb')
SUBMISSIONS_TABLE = os.environ['SUBMISSIONS_TABLE']
table = dynamodb.Table(SUBMISSIONS_TABLE)


def lambda_handler(event, context):
    try:
        path_params = event.get('pathParameters') or {}
        submission_id = path_params.get('submissionId')
        body = json.loads(event.get('body', '{}'))
        decision = (body.get('decision') or '').upper()
        reviewer = (body.get('reviewer') or 'officer').strip()
        notes = (body.get('notes') or '').strip()

        if not submission_id:
            return build_response(400, {'error': 'submissionId is required'})
        if decision not in (PAYMENT_APPROVED, PAYMENT_DECLINED):
            return build_response(400, {'error': f"decision must be {PAYMENT_APPROVED} or {PAYMENT_DECLINED}"})

        item = table.get_item(Key={'submissionId': submission_id}).get('Item')
        if not item:
            return build_response(404, {'error': 'Submission not found'})
        if item.get('paymentStatus') != PAYMENT_NEEDS_REVIEW:
            return build_response(400, {
                'error': f"Submission is not in {PAYMENT_NEEDS_REVIEW} state (current: {item.get('paymentStatus')})",
            })

        table.update_item(
            Key={'submissionId': submission_id},
            UpdateExpression=(
                'SET paymentStatus = :p, paymentReviewedBy = :r, paymentReviewNotes = :n, paymentDecidedAt = :t'
            ),
            ExpressionAttributeValues={
                ':p': decision,
                ':r': reviewer,
                ':n': notes,
                ':t': get_timestamp(),
            },
        )

        return build_response(200, {'submissionId': submission_id, 'paymentStatus': decision})

    except Exception as e:
        return build_response(500, {'error': str(e)})
