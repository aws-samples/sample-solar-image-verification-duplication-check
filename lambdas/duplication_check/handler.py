import base64
import json

import boto3

from constants import SIMILARITY_THRESHOLD
from db import get_connection

s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime')


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


def to_vector_literal(embedding: list[float]) -> str:
    return '[' + ','.join(str(v) for v in embedding) + ']'


def lambda_handler(event, context):
    submission_id = event['submissionId']
    s3_bucket = event['s3Bucket']
    s3_key = event['s3Key']

    embedding = get_image_embedding(s3_bucket, s3_key)
    vec = to_vector_literal(embedding)

    # pgvector cosine distance operator (<=>) with the HNSW index does the
    # nearest-neighbor search in-database; similarity = 1 - cosine_distance.
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT image_id, 1 - (embedding <=> %s::vector) AS similarity
            FROM image_embeddings
            ORDER BY embedding <=> %s::vector
            LIMIT 1
            """,
            (vec, vec),
        )
        row = cur.fetchone()

    max_similarity = float(row[1]) if row else 0.0
    matched_image_id = str(row[0]) if row else None

    passed = max_similarity < SIMILARITY_THRESHOLD
    result = {
        'passed': passed,
        'maxSimilarity': max_similarity,
        'matchedImageId': matched_image_id if not passed else None,
        'embedding': embedding,
    }

    event['duplicationCheckResult'] = result
    return event
