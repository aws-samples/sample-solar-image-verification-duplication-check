import os
import uuid
from decimal import Decimal

import boto3

from utils import get_timestamp

dynamodb = boto3.resource('dynamodb')
EMBEDDINGS_TABLE = os.environ['EMBEDDINGS_TABLE']
table = dynamodb.Table(EMBEDDINGS_TABLE)


def lambda_handler(event, context):
    submission_id = event['submissionId']
    s3_key = event['s3Key']
    embedding = event.get('duplicationCheckResult', {}).get('embedding', [])

    if not embedding:
        return event

    image_id = str(uuid.uuid4())
    table.put_item(Item={
        'imageId': image_id,
        'submissionId': submission_id,
        's3Key': s3_key,
        'embedding': [Decimal(str(v)) for v in embedding],
        'createdAt': get_timestamp(),
    })

    event['indexResult'] = {'imageId': image_id, 'indexed': True}
    return event
