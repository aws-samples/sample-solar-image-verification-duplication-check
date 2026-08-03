import json

from psycopg import sql

from utils import get_timestamp
from constants import STATUS_REJECTED
from db import get_connection


def lambda_handler(event, context):
    submission_id = event.get('submissionId')
    if not submission_id and 'error-info' in event:
        submission_id = event.get('error-info', {}).get('submissionId')

    final_decision = event.get('finalDecision', {})
    status = final_decision.get('status', STATUS_REJECTED)
    reason = final_decision.get('reason', 'unknown')

    if 'error-info' in event:
        err = event['error-info']
        status = STATUS_REJECTED
        reason = f"Pipeline error: {err.get('Error', 'Unknown')} - {err.get('Cause', 'Unknown')[:200]}"

    # Dynamic SET clause built with psycopg.sql composition — column names are
    # sql.Identifier objects (never string-interpolated), values are bound
    # parameters. Safe against SQL injection by construction.
    set_columns = ['status', 'completed_at', 'rejection_reason']
    values = [status, get_timestamp(), reason if status == STATUS_REJECTED else None]

    if 'qualityCheckResult' in event:
        qc = event['qualityCheckResult'].copy()
        qc.pop('passed', None)
        set_columns.append('quality_check_result')
        values.append(json.dumps(qc))

    if 'duplicationCheckResult' in event:
        dc = event['duplicationCheckResult'].copy()
        dc.pop('embedding', None)
        dc.pop('passed', None)
        set_columns.append('duplication_check_result')
        values.append(json.dumps(dc))

    values.append(submission_id)
    query = sql.SQL('UPDATE submissions SET {sets} WHERE submission_id = {sid}').format(
        sets=sql.SQL(', ').join(
            sql.SQL('{} = {}').format(sql.Identifier(col), sql.Placeholder())
            for col in set_columns
        ),
        sid=sql.Placeholder(),
    )
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(query, values)

    return {
        'submissionId': submission_id,
        'status': status,
        'reason': reason,
    }
