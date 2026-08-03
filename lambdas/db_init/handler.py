"""CloudFormation custom resource that bootstraps the PostgreSQL schema.

On stack Create/Update it enables the pgvector extension and creates the
`submissions` and `image_embeddings` tables plus the vector similarity index.
It is idempotent (IF NOT EXISTS everywhere) so repeated runs are safe. On
Delete it does nothing — the RDS instance is torn down with the stack.
"""

import json
import urllib.request

from db import get_connection

DDL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS submissions (
    submission_id            uuid PRIMARY KEY,
    user_id                  text NOT NULL,
    status                   text NOT NULL,
    s3_key                   text,
    s3_bucket                text,
    uploaded_at              timestamptz NOT NULL,
    completed_at             timestamptz,
    rejection_reason         text,
    quality_check_result     jsonb,
    duplication_check_result jsonb
);

CREATE INDEX IF NOT EXISTS submissions_user_uploaded_idx
    ON submissions (user_id, uploaded_at DESC);

CREATE TABLE IF NOT EXISTS image_embeddings (
    image_id      uuid PRIMARY KEY,
    submission_id uuid REFERENCES submissions (submission_id),
    s3_key        text,
    embedding     vector(1024),
    created_at    timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS image_embeddings_vec_idx
    ON image_embeddings USING hnsw (embedding vector_cosine_ops);
"""


def _send(event, context, status, reason=''):
    response_url = event.get('ResponseURL')
    if not response_url:
        return
    # CloudFormation ResponseURLs are always presigned https S3 URLs; reject
    # anything else (guards against file:// or custom-scheme injection).
    if not response_url.startswith('https://'):
        raise ValueError('ResponseURL must be https')
    body = json.dumps({
        'Status': status,
        'Reason': reason or f'See CloudWatch log stream: {context.log_stream_name}',
        'PhysicalResourceId': event.get('PhysicalResourceId') or context.log_stream_name,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': {},
    }).encode('utf-8')
    req = urllib.request.Request(response_url, data=body, method='PUT')
    req.add_header('content-type', '')
    req.add_header('content-length', str(len(body)))
    urllib.request.urlopen(req)


def lambda_handler(event, context):
    request_type = event.get('RequestType')
    try:
        if request_type in ('Create', 'Update'):
            conn = get_connection()
            with conn.cursor() as cur:
                cur.execute(DDL)
        _send(event, context, 'SUCCESS')
    except Exception as e:
        _send(event, context, 'FAILED', reason=str(e))
        raise
