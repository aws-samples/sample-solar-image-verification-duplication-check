import uuid

from utils import get_timestamp
from db import get_connection


def to_vector_literal(embedding: list[float]) -> str:
    return '[' + ','.join(str(v) for v in embedding) + ']'


def lambda_handler(event, context):
    submission_id = event['submissionId']
    s3_key = event['s3Key']
    embedding = event.get('duplicationCheckResult', {}).get('embedding', [])

    if not embedding:
        return event

    image_id = str(uuid.uuid4())
    vec = to_vector_literal(embedding)

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO image_embeddings
                (image_id, submission_id, s3_key, embedding, created_at)
            VALUES (%s, %s, %s, %s::vector, %s)
            """,
            (image_id, submission_id, s3_key, vec, get_timestamp()),
        )

    event['indexResult'] = {'imageId': image_id, 'indexed': True}
    return event
