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

Check 3 - Watermark & Internet Sourcing:
ONLY flag this check if you see concrete, visible evidence of watermarks or internet sourcing. Do NOT flag based on image quality, composition style, or professionalism alone — real installations can be photographed with good cameras.
Flag ONLY if you see:
- Visible watermark text, logos, or semi-transparent stamps overlaid on the image
- Stock photo agency identifiers physically present in the image (Getty, Shutterstock, iStock, Adobe Stock text/logos)
- Visible URL or website text embedded/overlaid on the image
- Screenshot artifacts (browser chrome, address bars, status bars, UI elements)
Do NOT consider high resolution, good lighting, clean composition, or professional quality as evidence of internet sourcing. Set is_internet_sourced to false unless you see explicit visual proof listed above.

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
  },
  "watermark": {
    "has_watermark": <boolean>,
    "is_internet_sourced": <boolean>,
    "confidence": "<high|medium|low>",
    "detected_marks": ["<mark1>", "<mark2>"],
    "notes": "<brief explanation>"
  }
}"""


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


MODEL_ID = 'google.gemma-3-12b-it'

MEDIA_TYPE_MAP = {
    'image/jpeg': 'jpeg',
    'image/png': 'png',
    'image/webp': 'webp',
}


def invoke_gemma(image_bytes: bytes, media_type: str) -> dict:
    format_str = MEDIA_TYPE_MAP.get(media_type, 'jpeg')

    response = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{
            'role': 'user',
            'content': [
                {
                    'image': {
                        'format': format_str,
                        'source': {'bytes': image_bytes},
                    },
                },
                {
                    'text': ANALYSIS_PROMPT,
                },
            ],
        }],
        inferenceConfig={
            'maxTokens': 1024,
            'temperature': 0.1,
        },
    )

    text = response['output']['message']['content'][0]['text']
    return parse_json_response(text)


def lambda_handler(event, context):
    submission_id = event['submissionId']
    s3_bucket = event['s3Bucket']
    s3_key = event['s3Key']

    obj = s3.get_object(Bucket=s3_bucket, Key=s3_key)
    image_bytes = obj['Body'].read()
    media_type = get_media_type(s3_key)

    analysis = invoke_gemma(image_bytes, media_type)

    inclination_ok = analysis.get('inclination', {}).get('acceptable', False)
    authenticity_ok = analysis.get('authenticity', {}).get('is_authentic', False)
    watermark = analysis.get('watermark', {})
    watermark_ok = not watermark.get('has_watermark', False) and not watermark.get('is_internet_sourced', False)
    passed = inclination_ok and authenticity_ok and watermark_ok

    reasons = []
    if not inclination_ok:
        angle = analysis.get('inclination', {}).get('estimated_angle', 'unknown')
        reasons.append(f"Inclination {angle}° outside acceptable range (20-40°)")
    if not authenticity_ok:
        signs = analysis.get('authenticity', {}).get('manipulation_signs', [])
        reasons.append(f"Image manipulation detected: {', '.join(signs)}")
    if not watermark_ok:
        marks = watermark.get('detected_marks', [])
        if watermark.get('has_watermark'):
            reasons.append(f"Watermark detected: {', '.join(marks) if marks else 'visible watermark found'}")
        if watermark.get('is_internet_sourced'):
            reasons.append("Image appears to be sourced from the internet")

    result = {
        'passed': passed,
        'inclination': analysis.get('inclination', {}),
        'authenticity': analysis.get('authenticity', {}),
        'watermark': watermark,
        'reason': '; '.join(reasons) if reasons else None,
    }

    event['customCheckResult'] = result
    return event
