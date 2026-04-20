import os

import boto3

from utils import get_timestamp, ensure_jpeg_bytes
from constants import (
    MIN_SOLAR_PANEL_CONFIDENCE,
    SOLAR_PANEL_LABELS,
    STATUS_PROCESSING,
)

rekognition = boto3.client('rekognition')
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

SUBMISSIONS_TABLE = os.environ['SUBMISSIONS_TABLE']
table = dynamodb.Table(SUBMISSIONS_TABLE)


def lambda_handler(event, context):
    submission_id = event['submissionId']
    s3_bucket = event['s3Bucket']
    s3_key = event['s3Key']

    table.update_item(
        Key={'submissionId': submission_id},
        UpdateExpression='SET #s = :s',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':s': STATUS_PROCESSING},
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
