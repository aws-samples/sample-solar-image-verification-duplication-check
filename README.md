# MNRE Solar Panel Verification Portal

A serverless AWS application for the **Ministry of New and Renewable Energy (MNRE)** that verifies solar panel installation images submitted for government subsidy claims. This POC runs a focused two-check pipeline: solar panel detection via Amazon Rekognition, followed by a duplicate-image check via Amazon Titan image embeddings.

---

## What It Does

1. User uploads a solar panel installation image through the web portal.
2. Quality Check (Amazon Rekognition) confirms the image actually shows a solar panel and screens for inappropriate content.
3. Duplication Check (Amazon Titan embeddings) confirms the image has not been submitted before.
4. Accepted images are indexed (embedding stored) so future submissions can be checked against them.
5. Final ACCEPTED / REJECTED status is written to DynamoDB with a full audit trail.

---

## Architecture

```
                          ┌──────────────┐
   User Browser  ◄──────► │  CloudFront  │ ◄──────►  S3 (Frontend static)
                          └──────┬───────┘
                                 │
                          ┌──────▼───────┐
                          │ API Gateway  │  (REST)
                          └──────┬───────┘
        ┌────────────────────────┼────────────────────────┐
        │                        │                         │
   POST /upload            POST /confirm         GET /status/{id}
   POST /confirm                 │               GET /submissions
        │                        │
   ┌────▼─────┐          ┌───────▼────────┐
   │ Upload λ │          │ ConfirmUpload λ │──► Step Functions
   └──────────┘          └────────────────┘         │
                                                     ▼
   ┌───────────────────── Step Functions pipeline (10-min timeout) ─────────────────────┐
   │                                                                                     │
   │  Wait 10s ─► Quality Check ─►[pass?]─► Duplication Check ─►[pass?]─► Index ─► Store  │
   │              (Rekognition)     │        (Titan embed)        │                       │
   │                                ▼                             ▼                       │
   │                          Reject+Store                  Reject+Store                  │
   │                                                                                     │
   │  [any step error] ─────────────────────────────────────────► StoreErrorResult      │
   └─────────────────────────────────────────────────────────────────────────────────────┘

   DynamoDB: Submissions (status + results)   |   Embeddings (1024-dim vectors)
   S3: uploaded images                        |   Bedrock: amazon.titan-embed-image-v1
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite 6, Framer Motion, Axios |
| CDN | Amazon CloudFront |
| API | Amazon API Gateway (REST) |
| Compute | AWS Lambda (Python 3.12, 6 handlers) |
| Orchestration | AWS Step Functions |
| Storage | Amazon S3, Amazon DynamoDB (on-demand) |
| AI/ML | Amazon Rekognition, Amazon Bedrock (Titan Image Embeddings) |
| Image processing | Pillow (PIL) via Lambda layer |
| IaC | AWS CDK (TypeScript) |
| Region | ap-south-1 (Mumbai) |

---

## Project Structure

```
mnre-solar-panel-poc/
├── cdk/                               # AWS CDK infrastructure
│   ├── bin/app.ts                     # CDK app entry point
│   └── lib/mnre-solar-panel-stack.ts  # Full stack definition
├── frontend/                          # React SPA (Vite + TypeScript)
│   └── src/
│       ├── api/client.ts              # Axios API client
│       ├── types/index.ts             # TypeScript interfaces
│       ├── App.tsx                    # Main app with polling
│       ├── App.css                    # Solar-themed styles
│       └── components/
│           ├── ImageUpload.tsx        # Drag-and-drop upload
│           ├── SubmissionsList.tsx    # Live-updating submissions list
│           ├── SubmissionDetail.tsx   # 4-step pipeline visualization
│           ├── DashboardStats.tsx     # Stats dashboard
│           ├── SolarScene.tsx         # Animated solar scene
│           ├── StatusBadge.tsx        # Animated status badges
│           └── ToastContainer.tsx     # Toast notifications
├── lambdas/                           # Lambda functions (Python 3.12)
│   ├── upload/                        # Pre-signed URL generation
│   ├── confirm_upload/                # S3 verification + Step Function start
│   ├── quality_check/                 # Rekognition solar detection + moderation
│   ├── duplication_check/             # Titan embedding similarity
│   ├── index_image/                   # Embedding storage for future lookups
│   ├── store_result/                  # Final status persistence
│   ├── get_status/                    # Status retrieval + auto-expiry
│   └── layers/common/                 # Shared utilities (Pillow, helpers)
├── deploy.py                          # End-to-end deploy script (wraps CDK)
└── README.md
```

---

## Verification Pipeline

The Step Functions state machine runs two checks sequentially. If either fails, the submission is rejected immediately and the result is stored.

### Step 1: Quality Check (Amazon Rekognition)

Lambda: `lambdas/quality_check/handler.py`

1. Converts the upload (PNG, WebP, BMP, TIFF, GIF) to JPEG via Pillow, saved back to S3 as `{name}_converted.jpg` and used by all downstream steps.
2. Calls Rekognition `DetectLabels` and matches solar-panel labels (`Solar Panel`, `Solar Energy`, `Solar Power`, `Electrical Device`, `Power Supply`), checking direct labels and parents. Highest match becomes `solarPanelConfidence`.
3. Passes if `solarPanelConfidence >= 70%`, else rejects with `"Solar panel not detected (confidence: X%)"`.
4. Calls Rekognition `DetectModerationLabels`; any moderation hit rejects the submission.

```json
{
  "passed": true,
  "solarPanelConfidence": 96.5,
  "labels": ["Electrical Device", "Solar Panels", "Architecture", "Building"],
  "reason": null
}
```

### Step 2: Duplication Check (Titan Image Embeddings)

Lambda: `lambdas/duplication_check/handler.py`

An image embedding represents a photo's visual content as 1,024 floating-point numbers. Visually similar images produce vectors pointing in nearly the same direction, so near-duplicates score high on cosine similarity.

1. Reads the converted image, base64-encodes it, and sends it to `amazon.titan-embed-image-v1` for a 1,024-dim vector.
2. Scans all stored embeddings from the Embeddings table (paginated).
3. Computes cosine similarity `(A · B) / (|A| × |B|)` against each.
4. Rejects as duplicate if max similarity `> 0.95`.
5. Passes the computed embedding forward so Index can store it without recomputing.

```json
{
  "passed": true,
  "maxSimilarity": 0.498,
  "matchedImageId": null,
  "embedding": [0.0234, -0.1567, "..."]
}
```

Scaling note: the duplication check does a full DynamoDB scan and in-memory comparison per request. Fine for POC scale; production should use a vector store (Aurora pgvector or OpenSearch).

### Step 3: Index Image

Lambda: `lambdas/index_image/handler.py` — stores the embedding (converted to `Decimal`) under a new `imageId`, linking `submissionId`, `s3Key`, and a timestamp. Only runs for accepted submissions.

### Step 4: Store Result

Lambda: `lambdas/store_result/handler.py` — writes final ACCEPTED / REJECTED plus check results and completion timestamp. Also the target of every step's error `Catch` block.

### Error handling & auto-expiry

- Each step has a `Catch` block routing exceptions to `StoreErrorResult` (marks REJECTED with error detail).
- A `Choice` after each check short-circuits to a reject path on failure.
- Get Status marks submissions stuck in PENDING/PROCESSING beyond 5 minutes as REJECTED.

---

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload` | Request a pre-signed S3 upload URL |
| POST | `/confirm` | Confirm upload, start the verification pipeline |
| GET | `/status/{submissionId}` | Single submission status + results |
| GET | `/submissions?userId=xxx` | All submissions for a user |

### Upload flow

```
1. POST /upload   { userId, fileName, contentType }  → { submissionId, uploadUrl }
2. PUT  uploadUrl  (binary image, direct to S3 via pre-signed URL)
3. POST /confirm  { submissionId }                   → verifies S3 object, starts Step Functions
```

### Payload format

`POST /upload` request:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `userId` | string | no (defaults `anonymous`) | User identifier |
| `fileName` | string | no (defaults `image.jpg`) | Original file name |
| `contentType` | string | no (defaults `image/jpeg`) | MIME type of the image |

`POST /upload` response:

```json
{ "submissionId": "uuid", "uploadUrl": "https://<bucket>.s3.amazonaws.com/..." }
```

---

## Data Models

### Submissions table

| Attribute | Type | Description |
|-----------|------|-------------|
| `submissionId` (PK) | String | UUID |
| `userId` | String | User identifier |
| `status` | String | PENDING / PROCESSING / ACCEPTED / REJECTED |
| `s3Key` | String | S3 object key (updated to converted JPEG) |
| `s3Bucket` | String | Bucket name |
| `uploadedAt` | String | ISO 8601 timestamp |
| `completedAt` | String | ISO 8601 timestamp (optional) |
| `rejectionReason` | String | Reason for rejection (optional) |
| `qualityCheckResult` | String (JSON) | Rekognition results |
| `duplicationCheckResult` | String (JSON) | Similarity scores + matched image ID |

GSI: `userId-index` (PK `userId`, SK `uploadedAt`)

### Embeddings table

| Attribute | Type | Description |
|-----------|------|-------------|
| `imageId` (PK) | String | UUID |
| `submissionId` | String | Linked submission |
| `s3Key` | String | S3 object key |
| `embedding` | List[Decimal] | 1,024-dim Titan vector |
| `createdAt` | String | ISO 8601 timestamp |

---

## Key Thresholds

| Parameter | Value |
|-----------|-------|
| Solar panel detection confidence | 70% |
| Duplicate similarity threshold | 95% |
| Stale submission auto-expiry | 5 minutes |
| Pre-signed URL validity | 5 minutes |
| Active submission polling | 3 seconds |
| Submission list polling | 6 seconds |
| Step Functions timeout | 10 minutes |

---

## Lambda Configuration

| Function | Memory | Timeout | Purpose |
|----------|--------|---------|---------|
| upload | 512 MB | 30s | Pre-signed URL generation |
| confirm_upload | 512 MB | 30s | S3 verification + Step Function start |
| quality_check | 512 MB | 120s | Rekognition detection + moderation |
| duplication_check | 1024 MB | 120s | Vector similarity computation |
| index_image | 512 MB | 30s | Embedding storage |
| store_result | 512 MB | 30s | Final result persistence |
| get_status | 512 MB | 30s | Status retrieval + auto-expiry |

---

## Prerequisites

- Node.js 18+
- Python 3.12
- AWS CLI configured for `ap-south-1`
- AWS CDK CLI (`npm install -g aws-cdk`)
- Bedrock model access for `amazon.titan-embed-image-v1`

---

## Deployment

Both deployment paths use the same AWS CDK stack under the hood — the difference is only how the source code reaches the machine that runs the deploy. Pick the use case that matches how the code is delivered.

### Use Case 1 — Source code delivered as a zip in the customer's S3 bucket

Use this when the project is packaged as a zip and dropped into an S3 bucket in the customer's AWS account (for example, handed off for the customer's own team or a CI runner to deploy). The deploy runs from inside the customer account against their credentials.

Prerequisites on the machine running the deploy (customer CloudShell, EC2, or a CI runner with an execution role):
- Node.js 18+, Python 3.12, AWS CLI, AWS CDK CLI (`npm install -g aws-cdk`)
- AWS credentials for the target account with permissions to deploy the stack (CloudFormation, Lambda, S3, DynamoDB, Step Functions, API Gateway, CloudFront, IAM)
- Bedrock model access enabled for `amazon.titan-embed-image-v1`

```bash
# 1. Download the source zip from the customer S3 bucket
aws s3 cp s3://<customer-bucket>/<path>/solar-rooftop-portal.zip . --region ap-south-1

# 2. Unzip and enter the project
unzip solar-rooftop-portal.zip -d solar-rooftop-portal
cd solar-rooftop-portal

# 3. Run the end-to-end deploy (installs deps, bootstraps, builds, deploys twice)
python3 deploy.py
```

`deploy.py` handles everything after unzip: `npm install` in `cdk/` and `frontend/`, `cdk bootstrap` (idempotent), the first `cdk deploy` to read the `ApiUrl`, writing `frontend/.env`, then a rebuild and second `cdk deploy` so CloudFront serves the API-connected frontend.

To package the repo into the zip that gets uploaded to S3 (exclude local build/dependency artifacts):

```bash
zip -r solar-rooftop-portal.zip . \
  -x '*/node_modules/*' '*/cdk.out/*' '*/dist/*' '*.git/*' 'cdk/outputs.json'
aws s3 cp solar-rooftop-portal.zip s3://<customer-bucket>/<path>/ --region ap-south-1
```

Tear down when finished:

```bash
python3 deploy.py --destroy
```

### Use Case 2 — Deploy directly with AWS CDK

Use this when you have the source checked out locally (e.g. cloned from Git) and want to deploy straight from your workstation.

Prerequisites:
- Node.js 18+, Python 3.12, AWS CLI configured for `ap-south-1`, AWS CDK CLI (`npm install -g aws-cdk`)
- Bedrock model access enabled for `amazon.titan-embed-image-v1`

Fastest path (same wrapper script):

```bash
python3 deploy.py                  # full deploy
python3 deploy.py --skip-install   # deps already installed
python3 deploy.py --destroy        # tear everything down
```

Manual CDK steps (equivalent to what `deploy.py` runs, useful for debugging a single stage):

```bash
# 1. Install dependencies
cd frontend && npm install && cd ..
cd cdk && npm install && cd ..

# 2. Bootstrap the account/region (one-time per account/region)
cd cdk && npx cdk bootstrap aws://ACCOUNT_ID/ap-south-1

# 3. Build the frontend, then deploy the stack
cd ../frontend && npm run build
cd ../cdk && npx cdk deploy

# 4. Wire the deployed API URL into the frontend and redeploy
cd ../frontend
echo "VITE_API_URL=https://xxxxxxxxxx.execute-api.ap-south-1.amazonaws.com/prod" > .env
npm run build
cd ../cdk && npx cdk deploy
```

### CDK outputs

Both use cases print these outputs on completion:

| Output | Description |
|--------|-------------|
| `ApiUrl` | REST API Gateway endpoint |
| `CloudFrontUrl` | Frontend application URL |
| `ImageBucketName` | S3 bucket for uploaded images |
| `SubmissionsTableName` | DynamoDB submissions table |
| `StateMachineArn` | Step Functions state machine ARN |

---

## Lambda Layer

Shared `common` layer (`lambdas/layers/common/python/`):

- `utils.py` — response builder, cosine similarity, timestamp helper, JPEG conversion
- `constants.py` — similarity threshold (0.95), min solar confidence (70%), solar label list, status values
- Pillow (PIL) — image format conversion, compiled for `manylinux2014_x86_64`

---

## Security Posture (POC)

- S3 buckets block all public access; uploads use pre-signed URLs
- Least-privilege IAM per Lambda
- DynamoDB reachable only via Lambda
- CORS open on API Gateway (all origins)
- No authentication — `userId` is a loose identifier (defaults to `demo-user` in the UI)

Production hardening: Cognito auth, JWT validation, API keys, restricted CORS, rate limiting, WAF, CloudWatch alarms, X-Ray tracing.

---

## Cleanup

```bash
python3 deploy.py --destroy
# or: cd cdk && npx cdk destroy
```

Removes all resources including S3 buckets (`RemovalPolicy.DESTROY` + `autoDeleteObjects`).
