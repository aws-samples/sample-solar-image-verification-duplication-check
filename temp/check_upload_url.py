#!/usr/bin/env python3
"""Print the presigned upload URL host to debug S3 307/403 issues."""
import json
import urllib.request

API = "https://0iz3hm6wyb.execute-api.ap-south-1.amazonaws.com/prod"

req = urllib.request.Request(
    f"{API}/upload",
    data=json.dumps({"userId": "debug", "fileName": "x.png", "contentType": "image/png"}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req) as r:
    body = json.loads(r.read())
print(body["uploadUrl"].split("?")[0])
