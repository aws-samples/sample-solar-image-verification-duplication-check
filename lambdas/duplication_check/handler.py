import base64
import json
import os

import boto3

from utils import cosine_similarity
from constants import SIMILARITY_THRESHOLD

s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')

SUBMISSIONS_TABLE = os.environ['SUBMISSIONS_TABLE']
EMBEDDINGS_TABLE = os.environ['EMBEDDINGS_TABLE']
BUCKET_NAME = os.environ['BUCKET_NAME']

submissions_table = dynamodb.Table(SUBMISSIONS_TABLE)
embeddings_table = dynamodb.Table(EMBEDDINGS_TABLE)


def get_image_embedding(bucket: str, key: str) -> list[float]:
    obj = s3.get_object(Bucket=bucket, Key=key)
    image_bytes = obj['Body'].read()
    base64_image = base64.b64encode(image_bytes).decode('utf-8')

    response = bedrock.invoke_model(
        modelId='amazon.titan-embed-image-v1',
        contentType='application/json',
        accept='application/json',
        body=json.dumps({'inputImage': base64_image}),
    )

    result = json.loads(response['body'].read())
    return result['embedding']


def scan_all_embeddings() -> list[dict]:
    items = []
    response = embeddings_table.scan()
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        response = embeddings_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    return items


def lambda_handler(event, context):
    submission_id = event['submissionId']
    s3_bucket = event['s3Bucket']
    s3_key = event['s3Key']

    embedding = get_image_embedding(s3_bucket, s3_key)

    existing = scan_all_embeddings()

    max_similarity = 0.0
    matched_image_id = None

    for item in existing:
        stored_embedding = [float(v) for v in item['embedding']]
        similarity = cosine_similarity(embedding, stored_embedding)
        if similarity > max_similarity:
            max_similarity = similarity
            matched_image_id = item['imageId']

    passed = max_similarity < SIMILARITY_THRESHOLD
    result = {
        'passed': passed,
        'maxSimilarity': float(max_similarity),
        'matchedImageId': matched_image_id if not passed else None,
        'embedding': embedding,
    }

    event['duplicationCheckResult'] = result
    return event
