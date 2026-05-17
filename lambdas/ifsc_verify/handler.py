import json
import urllib.error
import urllib.request

IFSC_API_BASE = 'https://ifsc.razorpay.com'
TIMEOUT_SECONDS = 5


def fetch_ifsc(ifsc: str) -> dict:
    url = f"{IFSC_API_BASE}/{ifsc}"
    req = urllib.request.Request(url, headers={'User-Agent': 'mnre-solar-poc/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
            return {'found': True, 'data': payload}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {'found': False, 'error': 'IFSC not found'}
        return {'found': False, 'error': f'HTTP {e.code}'}
    except urllib.error.URLError as e:
        return {'found': False, 'error': f'Network error: {e.reason}'}


def lambda_handler(event, context):
    ocr = event.get('chequeOcrResult', {})
    ifsc = (ocr.get('ifsc') or '').strip().upper()

    result = {'ifsc': ifsc, 'apiCalled': False, 'verified': False}

    if not ocr.get('ifscFormatValid'):
        result['error'] = 'IFSC format invalid or missing'
        event['ifscVerifyResult'] = result
        return event

    api = fetch_ifsc(ifsc)
    result['apiCalled'] = True

    if not api.get('found'):
        result['error'] = api.get('error', 'IFSC not found')
        event['ifscVerifyResult'] = result
        return event

    data = api['data']
    result.update({
        'verified': True,
        'bank': data.get('BANK', ''),
        'branch': data.get('BRANCH', ''),
        'address': data.get('ADDRESS', ''),
        'city': data.get('CITY', ''),
        'state': data.get('STATE', ''),
        'micr': data.get('MICR', ''),
        'imps': bool(data.get('IMPS', False)),
        'neft': bool(data.get('NEFT', False)),
        'rtgs': bool(data.get('RTGS', False)),
        'upi': bool(data.get('UPI', False)),
    })

    event['ifscVerifyResult'] = result
    return event
