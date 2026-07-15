"""S3 event-notification intake for batch image validation.

Triggered when objects are created in the batch intake bucket. For each image,
registers a submission row in PostgreSQL and starts the same Step Functions
verification pipeline used by the portal upload flow.

Skips the `_converted.jpg` artifacts written back by quality_check to avoid
re-triggering the pipeline on its own output.
"""

import json
import os
import urllib.parse
import uuid

import boto3

from utils import get_timestamp
from constants import STATUS_PENDING
from db import get_connection

sfn = boto3.client('stepfunctions')

STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.gif')


def lambda_handler(event, context):
    started = []
    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(record['s3']['object']['key'])

        lower = key.lower()
        if not lower.endswith(IMAGE_EXTENSIONS):
            continue
        if '_converted.jpg' in lower:
            continue  # pipeline artifact from quality_check, not a new upload

        submission_id = str(uuid.uuid4())

        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO submissions
                    (submission_id, user_id, s3_key, s3_bucket, status, uploaded_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (submission_id, 'batch-upload', key, bucket, STATUS_PENDING, get_timestamp()),
            )

        sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=submission_id,
            input=json.dumps({
                'submissionId': submission_id,
                's3Bucket': bucket,
                's3Key': key,
            }),
        )
        started.append(submission_id)

    return {'started': started, 'count': len(started)}
