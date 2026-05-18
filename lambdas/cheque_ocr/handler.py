import json
import os
import re

import boto3

s3 = boto3.client('s3')

BEDROCK_REGION = os.environ.get('BEDROCK_REGION', 'ap-south-1')
MODEL_ID = os.environ.get('CHEQUE_MODEL_ID', 'anthropic.claude-opus-4-7')

bedrock = boto3.client('bedrock-runtime', region_name=BEDROCK_REGION)

OCR_PROMPT = """You are extracting structured fields from an Indian bank cancelled cheque. Return ONLY valid JSON, no commentary.

Extract these fields from the cheque image:
- ifsc: The IFSC code (11 characters, format: 4 letters + 0 + 6 alphanumeric, e.g. SBIN0007974). Look near "IFSC" label.
- accountNumber: The account number (digits only, no spaces).
- holderName: The account holder name as printed on the cheque.
- bankName: The bank name as printed on the cheque (e.g. "State Bank of India").
- branch: The branch name/location printed on the cheque.
- micr: The MICR code (9 digits) usually printed at the bottom.
- hasCancelledStamp: true if the word "CANCELLED" or "CANCELED" is visibly written/stamped across the cheque (handwritten or stamped). false otherwise.
- hasSignature: true if a signature is visible, false otherwise.
- ocrConfidence: a number between 0 and 1 representing your overall confidence in the extracted fields.

If a field cannot be read, return an empty string for it (or false for booleans). Do not invent values.

Respond ONLY with this JSON:
{
  "ifsc": "<string>",
  "accountNumber": "<string>",
  "holderName": "<string>",
  "bankName": "<string>",
  "branch": "<string>",
  "micr": "<string>",
  "hasCancelledStamp": <boolean>,
  "hasSignature": <boolean>,
  "ocrConfidence": <number>
}"""


MEDIA_TYPE_MAP = {
    'image/jpeg': 'jpeg',
    'image/png': 'png',
    'image/webp': 'webp',
}


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
    return json.loads(cleaned.strip())


def invoke_opus(image_bytes: bytes, media_type: str) -> dict:
    format_str = MEDIA_TYPE_MAP.get(media_type, 'jpeg')

    response = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{
            'role': 'user',
            'content': [
                {'image': {'format': format_str, 'source': {'bytes': image_bytes}}},
                {'text': OCR_PROMPT},
            ],
        }],
        inferenceConfig={'maxTokens': 1024},
    )

    text = response['output']['message']['content'][0]['text']
    return parse_json_response(text)


def lambda_handler(event, context):
    submission_id = event['submissionId']
    s3_bucket = event['s3Bucket']
    cheque_key = event['chequeS3Key']

    obj = s3.get_object(Bucket=s3_bucket, Key=cheque_key)
    image_bytes = obj['Body'].read()
    media_type = get_media_type(cheque_key)

    extracted = invoke_opus(image_bytes, media_type)

    ifsc = (extracted.get('ifsc') or '').strip().upper()
    extracted['ifsc'] = ifsc
    extracted['ifscFormatValid'] = bool(re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc))

    event['chequeOcrResult'] = extracted
    return event
