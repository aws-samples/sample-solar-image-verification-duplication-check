import boto3

from utils import ensure_jpeg_bytes
from constants import (
    MIN_SOLAR_PANEL_CONFIDENCE,
    SOLAR_PANEL_LABELS,
    STATUS_PROCESSING,
)
from db import get_connection

rekognition = boto3.client('rekognition')
s3 = boto3.client('s3')


def lambda_handler(event, context):
    submission_id = event['submissionId']
    s3_bucket = event['s3Bucket']
    s3_key = event['s3Key']

    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(
            'UPDATE submissions SET status = %s WHERE submission_id = %s',
            (STATUS_PROCESSING, submission_id),
        )

    obj = s3.get_object(Bucket=s3_bucket, Key=s3_key)
    image_bytes = obj['Body'].read()

    jpeg_bytes = ensure_jpeg_bytes(image_bytes)

    converted_key = s3_key.rsplit('.', 1)[0] + '_converted.jpg'
    s3.put_object(Bucket=s3_bucket, Key=converted_key, Body=jpeg_bytes, ContentType='image/jpeg')

    event['s3Key'] = converted_key

    response = rekognition.detect_labels(
        Image={'S3Object': {'Bucket': s3_bucket, 'Name': converted_key}},
        MaxLabels=25,
        MinConfidence=50,
    )

    labels = response.get('Labels', [])
    label_names = [l['Name'] for l in labels]

    solar_confidence = 0.0
    for label in labels:
        if label['Name'] in SOLAR_PANEL_LABELS:
            solar_confidence = max(solar_confidence, label['Confidence'])
        for parent in label.get('Parents', []):
            if parent['Name'] in SOLAR_PANEL_LABELS:
                solar_confidence = max(solar_confidence, label['Confidence'])

    passed = solar_confidence >= MIN_SOLAR_PANEL_CONFIDENCE
    reason = None if passed else f"Solar panel not detected (confidence: {solar_confidence:.1f}%)"

    moderation = rekognition.detect_moderation_labels(
        Image={'S3Object': {'Bucket': s3_bucket, 'Name': converted_key}},
        MinConfidence=75,
    )
    moderation_labels = moderation.get('ModerationLabels', [])
    if moderation_labels:
        passed = False
        reason = f"Image flagged for inappropriate content: {', '.join(m['Name'] for m in moderation_labels)}"

    result = {
        'passed': passed,
        'solarPanelConfidence': solar_confidence,
        'labels': label_names[:10],
        'reason': reason,
    }

    event['qualityCheckResult'] = result
    return event
