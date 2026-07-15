#!/usr/bin/env python3
"""End-to-end test for the Solar Portal pipeline (RDS + pgvector).

Uploads an image via the API, polls until a final status, prints results.
Run twice with the same image to verify duplicate rejection.

Usage:
    python3 temp/e2e_test.py test-images/test1.png
"""

import json
import mimetypes
import sys
import time
import urllib.request

API = "https://0iz3hm6wyb.execute-api.ap-south-1.amazonaws.com/prod"


def post(path, payload):
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def get(path):
    with urllib.request.urlopen(f"{API}{path}") as r:
        return json.loads(r.read())


def put_file(url, file_path, content_type):
    # curl follows S3 307 redirects and re-sends the PUT body (urllib does not)
    import subprocess
    result = subprocess.run(
        ["curl", "-sS", "-L", "-o", "/dev/null", "-w", "%{http_code}",
         "-X", "PUT", "-H", f"Content-Type: {content_type}",
         "--data-binary", f"@{file_path}", url],
        capture_output=True, text=True,
    )
    return int(result.stdout.strip() or 0)


def main():
    image = sys.argv[1] if len(sys.argv) > 1 else "test-images/test1.png"
    content_type = mimetypes.guess_type(image)[0] or "image/png"
    file_name = image.split("/")[-1]

    print(f"1. Requesting upload URL for {file_name} ({content_type})")
    up = post("/upload", {"userId": "e2e-test", "fileName": file_name, "contentType": content_type})
    sid = up["submissionId"]
    print(f"   submissionId: {sid}")

    print("2. Uploading image to S3")
    status = put_file(up["uploadUrl"], image, content_type)
    print(f"   PUT status: {status}")

    print("3. Confirming upload (starts pipeline)")
    conf = post("/confirm", {"submissionId": sid})
    print(f"   {conf}")

    print("4. Polling status...")
    for i in range(40):
        time.sleep(6)
        s = get(f"/status/{sid}")
        st = s.get("status")
        print(f"   [{i*6:>3}s] {st}")
        if st in ("ACCEPTED", "REJECTED"):
            print("\n=== FINAL RESULT ===")
            print(json.dumps(s, indent=2))
            return
    print("Timed out waiting for final status")
    sys.exit(1)


if __name__ == "__main__":
    main()
