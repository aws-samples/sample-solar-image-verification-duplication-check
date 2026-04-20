import base64
import json
import os
import re

import boto3

s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')

SUBMISSIONS_TABLE = os.environ['SUBMISSIONS_TABLE']
BUCKET_NAME = os.environ['BUCKET_NAME']

table = dynamodb.Table(SUBMISSIONS_TABLE)

ANALYSIS_PROMPT = """You are an expert solar panel installation inspector working for India's Ministry of New and Renewable Energy (MNRE).
Analyze this solar panel installation image and provide your assessment in JSON format.

Check 1 - Inclination:
Estimate the tilt angle of the solar panel(s) from horizontal. For India (MNRE guidelines), the optimal tilt is approximately 30 degrees (acceptable range: 20-40 degrees from horizontal). Report the estimated angle.

Check 2 - Image Authenticity:
Examine the image for signs of digital manipulation including:
- Inconsistent lighting or shadows
- Warping or distortion artifacts
- Clone stamping patterns
- Unnatural edge boundaries around the solar panels
- Compression artifacts inconsistent with a single capture
- Signs of image compositing or splicing

Respond ONLY with this JSON (no additional text):
{
  "inclination": {
    "estimated_angle": <number>,
    "acceptable": <boolean>,
    "confidence": "<high|medium|low>",
    "notes": "<brief explanation>"
  },
  "authenticity": {
    "is_authentic": <boolean>,
    "confidence": "<high|medium|low>",
    "manipulation_signs": ["<sign1>", "<sign2>"],
    "notes": "<brief explanation>"
  }
}"""

MODEL_IDS = [
    'global.anthropic.claude-opus-4-7',
    'apac.anthropic.claude-sonnet-4-20250514-v1:0',
]


def get_media_type(key: str) -> str:
    ext = key.rsplit('.', 1)[-1].lower()
    return {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp',
    }.get(ext, 'image/jpeg')


def parse_json_response(text: str) -> dict:
    cleaned = re.sub(r'```json\s*', '', text)
    cleaned = re.sub(r'```\s*', '', cleaned)
    cleaned = cleaned.strip()
    return json.loads(cleaned)


def invoke_claude(base64_image: str, media_type: str) -> dict:
    body = json.dumps({
        'anthropic_version': 'bedrock-2023-05-31',
        'max_tokens': 1024,
        'messages': [{
            'role': 'user',
            'content': [
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': media_type,
                        'data': base64_image,
                    },
                },
                {
                    'type': 'text',
                    'text': ANALYSIS_PROMPT,
                },
            ],
        }],
    })

    last_error = None
    for model_id in MODEL_IDS:
        try:
            response = bedrock.invoke_model(
                modelId=model_id,
                contentType='application/json',
                accept='application/json',
                body=body,
            )
            result = json.loads(response['body'].read())
            return parse_json_response(result['content'][0]['text'])
        except Exception as e:
            last_error = e
            continue

    raise last_error


def lambda_handler(event, context):
    submission_id = event['submissionId']
    s3_bucket = event['s3Bucket']
    s3_key = event['s3Key']

    obj = s3.get_object(Bucket=s3_bucket, Key=s3_key)
    image_bytes = obj['Body'].read()
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    media_type = get_media_type(s3_key)

    analysis = invoke_claude(base64_image, media_type)

    inclination_ok = analysis.get('inclination', {}).get('acceptable', False)
    authenticity_ok = analysis.get('authenticity', {}).get('is_authentic', False)
    passed = inclination_ok and authenticity_ok

    reasons = []
    if not inclination_ok:
        angle = analysis.get('inclination', {}).get('estimated_angle', 'unknown')
        reasons.append(f"Inclination {angle}° outside acceptable range (20-40°)")
    if not authenticity_ok:
        signs = analysis.get('authenticity', {}).get('manipulation_signs', [])
        reasons.append(f"Image manipulation detected: {', '.join(signs)}")

    result = {
        'passed': passed,
        'inclination': analysis.get('inclination', {}),
        'authenticity': analysis.get('authenticity', {}),
        'reason': '; '.join(reasons) if reasons else None,
    }

    event['customCheckResult'] = result
    return event
