import json
from datetime import datetime, timezone, timedelta

from utils import build_response, get_timestamp
from constants import STATUS_REJECTED
from db import get_connection

STALE_THRESHOLD_MINUTES = 5

COLUMNS = [
    'submission_id', 'user_id', 'status', 'uploaded_at', 'completed_at',
    'rejection_reason', 'quality_check_result', 'duplication_check_result',
]


def _iso(value) -> str:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def row_to_dict(row: tuple) -> dict:
    item = dict(zip(COLUMNS, row))
    item = auto_expire_stale(item)
    result = {
        'submissionId': str(item['submission_id']),
        'userId': item.get('user_id') or '',
        'status': item.get('status') or 'UNKNOWN',
        'uploadedAt': _iso(item.get('uploaded_at')) or '',
        'completedAt': _iso(item.get('completed_at')),
        'rejectionReason': item.get('rejection_reason'),
    }
    if item.get('quality_check_result') is not None:
        result['qualityCheckResult'] = item['quality_check_result']
    if item.get('duplication_check_result') is not None:
        result['duplicationCheckResult'] = item['duplication_check_result']
    return result


def auto_expire_stale(item: dict) -> dict:
    status = item.get('status', '')
    if status not in ('PENDING', 'PROCESSING'):
        return item

    uploaded = item.get('uploaded_at')
    if not uploaded:
        return item

    upload_time = uploaded if isinstance(uploaded, datetime) else datetime.fromisoformat(str(uploaded))
    now = datetime.now(timezone.utc)
    if (now - upload_time) > timedelta(minutes=STALE_THRESHOLD_MINUTES):
        reason = 'Pipeline timed out - verification did not complete within 5 minutes'
        ts = get_timestamp()
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                'UPDATE submissions SET status = %s, rejection_reason = %s, completed_at = %s '
                'WHERE submission_id = %s',
                (STATUS_REJECTED, reason, ts, item['submission_id']),
            )
        item['status'] = STATUS_REJECTED
        item['rejection_reason'] = reason
        item['completed_at'] = ts
    return item


def lambda_handler(event, context):
    path_params = event.get('pathParameters') or {}
    query_params = event.get('queryStringParameters') or {}

    col_list = ', '.join(COLUMNS)
    conn = get_connection()

    submission_id = path_params.get('submissionId')
    if submission_id:
        with conn.cursor() as cur:
            cur.execute(
                f'SELECT {col_list} FROM submissions WHERE submission_id = %s',
                (submission_id,),
            )
            row = cur.fetchone()
        if not row:
            return build_response(404, {'error': 'Submission not found'})
        return build_response(200, row_to_dict(row))

    user_id = query_params.get('userId')
    if user_id:
        with conn.cursor() as cur:
            cur.execute(
                f'SELECT {col_list} FROM submissions WHERE user_id = %s '
                'ORDER BY uploaded_at DESC',
                (user_id,),
            )
            rows = cur.fetchall()
        return build_response(200, [row_to_dict(r) for r in rows])

    return build_response(400, {'error': 'Provide submissionId or userId'})
