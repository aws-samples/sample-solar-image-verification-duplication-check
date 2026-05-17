import json
import os

import boto3

from utils import get_timestamp, name_similarity
from constants import (
    PAYMENT_APPROVED,
    PAYMENT_DECLINED,
    PAYMENT_NEEDS_REVIEW,
    CHEQUE_NAME_MATCH_THRESHOLD,
    CHEQUE_BANK_MATCH_THRESHOLD,
    CHEQUE_OCR_CONFIDENCE_THRESHOLD,
    CHEQUE_STAMP_CONFIDENCE_THRESHOLD,
)

dynamodb = boto3.resource('dynamodb')
SUBMISSIONS_TABLE = os.environ['SUBMISSIONS_TABLE']
table = dynamodb.Table(SUBMISSIONS_TABLE)


def evaluate(ocr: dict, ifsc: dict, expected_holder: str) -> dict:
    hard_fails: list[str] = []
    soft_fails: list[str] = []

    if not ifsc.get('verified'):
        hard_fails.append(f"IFSC verification failed: {ifsc.get('error', 'unknown')}")
    if not ocr.get('hasCancelledStamp'):
        hard_fails.append("Cheque does not show 'CANCELLED' marking")

    account_number = (ocr.get('accountNumber') or '').replace(' ', '')
    if not account_number or len(account_number) < 9 or not account_number.isdigit():
        hard_fails.append('Account number missing or invalid')

    bank_match_score = 0.0
    if ifsc.get('verified'):
        bank_match_score = name_similarity(ocr.get('bankName', ''), ifsc.get('bank', ''))
        if bank_match_score < CHEQUE_BANK_MATCH_THRESHOLD:
            soft_fails.append(
                f"Bank name on cheque ('{ocr.get('bankName', '')}') does not match IFSC API "
                f"('{ifsc.get('bank', '')}'); similarity {bank_match_score:.2f}"
            )

    name_match_score = name_similarity(ocr.get('holderName', ''), expected_holder)
    if name_match_score < CHEQUE_NAME_MATCH_THRESHOLD:
        soft_fails.append(
            f"Holder name on cheque ('{ocr.get('holderName', '')}') does not match applicant "
            f"('{expected_holder}'); similarity {name_match_score:.2f}"
        )

    ocr_confidence = float(ocr.get('ocrConfidence') or 0.0)
    if ocr_confidence < CHEQUE_OCR_CONFIDENCE_THRESHOLD:
        soft_fails.append(f"Low OCR confidence ({ocr_confidence:.2f})")

    if hard_fails:
        status = PAYMENT_DECLINED
    elif soft_fails:
        status = PAYMENT_NEEDS_REVIEW
    else:
        status = PAYMENT_APPROVED

    return {
        'paymentStatus': status,
        'hardFails': hard_fails,
        'softFails': soft_fails,
        'bankMatchScore': bank_match_score,
        'nameMatchScore': name_match_score,
        'ocrConfidence': ocr_confidence,
    }


def lambda_handler(event, context):
    submission_id = event['submissionId']
    ocr = event.get('chequeOcrResult', {})
    ifsc = event.get('ifscVerifyResult', {})
    expected_holder = event.get('expectedHolderName', '')

    decision = evaluate(ocr, ifsc, expected_holder)

    cheque_validation = {
        'ifsc': ocr.get('ifsc', ''),
        'accountNumber': ocr.get('accountNumber', ''),
        'holderName': ocr.get('holderName', ''),
        'bankName': ocr.get('bankName', ''),
        'branch': ocr.get('branch', ''),
        'micr': ocr.get('micr', ''),
        'hasCancelledStamp': bool(ocr.get('hasCancelledStamp', False)),
        'hasSignature': bool(ocr.get('hasSignature', False)),
        'ifscApiBank': ifsc.get('bank', ''),
        'ifscApiBranch': ifsc.get('branch', ''),
        'ifscApiAddress': ifsc.get('address', ''),
        'ifscVerified': bool(ifsc.get('verified', False)),
        'ifscError': ifsc.get('error'),
        'bankMatchScore': decision['bankMatchScore'],
        'nameMatchScore': decision['nameMatchScore'],
        'ocrConfidence': decision['ocrConfidence'],
        'hardFails': decision['hardFails'],
        'softFails': decision['softFails'],
    }

    table.update_item(
        Key={'submissionId': submission_id},
        UpdateExpression='SET paymentStatus = :p, chequeValidationResult = :r, paymentDecidedAt = :t',
        ExpressionAttributeValues={
            ':p': decision['paymentStatus'],
            ':r': json.dumps(cheque_validation),
            ':t': get_timestamp(),
        },
    )

    return {
        'submissionId': submission_id,
        'paymentStatus': decision['paymentStatus'],
        'chequeValidationResult': cheque_validation,
    }
