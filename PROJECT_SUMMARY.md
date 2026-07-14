# MNRE Solar Panel Verification Portal — Project Summary

## Overview

A serverless AWS application built as a Proof-of-Concept for the **Ministry of New and Renewable Energy (MNRE)**, India. It verifies solar panel installation images submitted for government subsidy eligibility. This POC scope runs a two-check verification pipeline: solar panel detection (Rekognition) and duplicate-image detection (Titan embeddings).

**Deployment Region**: `ap-south-1` (Mumbai, India)

---

## Tech Stack

| Layer              | Technology                                                    |
|--------------------|---------------------------------------------------------------|
| **Frontend**       | React 19, TypeScript, Vite 6, Framer Motion 12, Axios, React Dropzone |
| **Backend**        | Python 3.12 on AWS Lambda (6 handlers)                        |
| **Orchestration**  | AWS Step Functions (state machine)                            |
| **Database**       | Amazon DynamoDB (2 tables, on-demand billing)                 |
| **Storage**        | Amazon S3 (images + frontend static assets)                   |
| **CDN**            | Amazon CloudFront                                             |
| **API**            | Amazon API Gateway (REST)                                     |
| **AI/ML**          | Amazon Rekognition, Amazon Titan Image Embeddings (via AWS Bedrock) |
| **IaC**            | AWS CDK 2.170 (TypeScript)                                    |
| **Image Processing**| Pillow (PIL) via Lambda Layer                                |

---

## Architecture

```
User Browser
    |
CloudFront CDN  <-->  S3 (Frontend Static)
    |
API Gateway (REST)
    |-- POST /upload         --> Upload Lambda
    |-- POST /confirm        --> Confirm Upload Lambda --> Step Functions
    |-- GET  /status/{id}    --> Get Status Lambda
    |-- GET  /submissions?userId=X --> Get Status Lambda

Step Functions Pipeline (10-min timeout):
    1. Wait 10s
    2. Quality Check (Rekognition)
    3. [Decision] If PASS --> Duplication Check, else --> Reject
    4. Duplication Check (Titan Embeddings)
    5. [Decision] If PASS --> Index Image, else --> Reject
    6. Index Image (Store Embedding in DynamoDB)
    7. Accept & Store Result

    [Error at any step] --> Store Error Result (REJECTED)
```

---

## Verification Pipeline (2 Checks + Index + Store)

### Step 1: Quality Check — Amazon Rekognition
- Converts uploaded image to JPEG via Pillow (supports PNG, WebP, BMP, TIFF, GIF)
- Runs `DetectLabels` for solar panel detection (minimum **70% confidence**)
- Matched labels: "Solar Panel", "Solar Energy", "Solar Power", "Electrical Device", "Power Supply"
- Runs `DetectModerationLabels` to flag inappropriate content
- **Fail**: Immediately rejects submission

### Step 2: Duplication Check — Titan Embeddings
- Generates **1024-dimensional** image embedding via `amazon.titan-embed-image-v1`
- Computes cosine similarity against all stored embeddings
- Threshold: **< 95% similarity** to pass
- **Fail**: Rejects as duplicate

### Step 3: Image Indexing
- Stores the embedding vector in DynamoDB Embeddings table
- Associates with submission ID and S3 key for future duplicate detection
- Only runs for accepted submissions

### Step 4: Store Result
- Updates submission record with final status (ACCEPTED / REJECTED)
- Preserves all check results as JSON for complete audit trail
- Records completion timestamp and rejection reason (if applicable)

---

## API Endpoints

| Method | Endpoint                    | Purpose                                      |
|--------|-----------------------------|----------------------------------------------|
| POST   | `/upload`                   | Generate pre-signed S3 URL for image upload   |
| PUT    | `{presigned S3 URL}`        | Client uploads image directly to S3           |
| POST   | `/confirm`                  | Verify S3 upload, start verification pipeline |
| GET    | `/status/{submissionId}`    | Retrieve single submission status + results   |
| GET    | `/submissions?userId={id}`  | List all submissions for a user               |

---

## Data Models

### Submissions Table (DynamoDB)

| Attribute                | Type   | Description                              |
|--------------------------|--------|------------------------------------------|
| `submissionId` (PK)     | String | UUID                                     |
| `userId`                 | String | User identifier                          |
| `status`                 | String | PENDING / PROCESSING / ACCEPTED / REJECTED |
| `s3Key`                  | String | S3 object key                            |
| `s3Bucket`               | String | Bucket name                              |
| `uploadedAt`             | String | ISO 8601 timestamp                       |
| `completedAt`            | String | ISO 8601 timestamp (optional)            |
| `rejectionReason`        | String | Reason for rejection (optional)          |
| `qualityCheckResult`     | String | JSON — Rekognition results               |
| `duplicationCheckResult` | String | JSON — Similarity check results          |

**GSI**: `userId-index` (PK: `userId`, SK: `uploadedAt`)

### Embeddings Table (DynamoDB)

| Attribute           | Type         | Description                      |
|---------------------|--------------|----------------------------------|
| `imageId` (PK)     | String       | UUID                             |
| `submissionId`      | String       | Linked submission ID             |
| `s3Key`             | String       | Object path in S3                |
| `embedding`         | List[Decimal]| 1024-dimensional Titan vector    |
| `createdAt`         | String       | ISO 8601 timestamp               |

---

## Frontend Components

| Component            | Description                                                          |
|----------------------|----------------------------------------------------------------------|
| **ImageUpload**      | Drag-and-drop uploader (JPG, PNG, WebP, BMP, TIFF, GIF; max 15 MB) |
| **SubmissionDetail** | 4-step pipeline visualization with animated progress indicators      |
| **SubmissionsList**  | Scrollable list of all user submissions with status badges           |
| **DashboardStats**   | 4-card summary (Total, In Progress, Accepted, Rejected)             |
| **SolarScene**       | Animated decorative scene (sun, solar rays, panels, energy particles)|
| **StatusBadge**      | Color-coded status indicators                                        |
| **ToastContainer**   | Auto-dismissing notification toasts                                  |

**Design Theme**: India flag colors (saffron, white, green) in header accent bar; solar gold/orange accents; Framer Motion animations throughout; Inter font family.

---

## Key Thresholds & Parameters

| Parameter                        | Value       |
|----------------------------------|-------------|
| Solar Panel Detection Confidence | 70%         |
| Duplicate Similarity Threshold   | 95%         |
| Stale Submission Auto-Expiry     | 5 minutes   |
| Pre-signed URL Validity          | 5 minutes   |
| Active Submission Polling        | 3 seconds   |
| Submission List Polling          | 6 seconds   |
| Step Functions Timeout           | 10 minutes  |

---

## Lambda Configuration

| Function           | Memory  | Timeout | Purpose                           |
|--------------------|---------|---------|-----------------------------------|
| upload             | 512 MB  | 30s     | Pre-signed URL generation         |
| confirm_upload     | 512 MB  | 30s     | S3 verification + Step Function start |
| quality_check      | 512 MB  | 120s    | Rekognition image analysis        |
| duplication_check  | 1024 MB | 120s    | Vector similarity computation     |
| index_image        | 512 MB  | 30s     | Embedding storage                 |
| store_result       | 512 MB  | 30s     | Final result persistence          |
| get_status         | 512 MB  | 30s     | Status retrieval                  |

---

## Project Structure

```
mnre-solar-panel-poc/
├── frontend/                        # React SPA (Vite + TypeScript)
│   └── src/
│       ├── api/client.ts            # Axios API client
│       ├── types/index.ts           # TypeScript interfaces
│       └── components/              # UI components (7 total)
├── cdk/                             # AWS CDK Infrastructure
│   └── lib/mnre-solar-panel-stack.ts  # Full stack definition
├── lambdas/                         # 6 Lambda functions (Python 3.12)
│   ├── upload/
│   ├── confirm_upload/
│   ├── quality_check/
│   ├── duplication_check/
│   ├── index_image/
│   ├── store_result/
│   ├── get_status/
│   └── layers/common/              # Shared utilities + Pillow
│       └── python/
│           ├── utils.py             # Response builder, cosine similarity, JPEG conversion
│           └── constants.py         # Thresholds, status values, labels
├── deploy.py                        # End-to-end deploy script (wraps CDK)
└── README.md
```

---

## Key Design Decisions

| Decision                                | Rationale                                                   |
|-----------------------------------------|-------------------------------------------------------------|
| **Serverless architecture**             | Auto-scaling, zero idle cost, no server management          |
| **Direct S3 upload (pre-signed URLs)**  | Reduces Lambda bandwidth costs, improves reliability        |
| **Sequential pipeline with early exit** | Clear audit trail, stops expensive operations early         |
| **Vector embeddings for deduplication** | Detects near-duplicates (not just exact hash matches)       |
| **5-minute auto-expiry**                | Handles crashed/timed-out pipelines gracefully              |
| **ap-south-1 (Mumbai) deployment**      | Low latency for India users, data residency compliance      |
| **DynamoDB on-demand billing**          | No capacity provisioning, scales automatically              |
| **10-second initial wait in pipeline**  | Mitigates Lambda cold-start latency                         |

---

## Security Posture (Current — POC)

- S3 buckets block all public access; uploads use pre-signed URLs
- Least-privilege IAM policies per Lambda function
- DynamoDB accessible only via Lambda (no direct internet access)
- CORS enabled on API Gateway for all origins
- **No authentication** — uses `userId` as a loose identifier (hardcoded "demo-user")

**Production Recommendations**: Cognito auth, JWT validation at API Gateway, API keys, restricted CORS, rate limiting, WAF, CloudWatch alarms, X-Ray tracing.

---

## Deployment

```bash
# One-command end-to-end deploy
python3 deploy.py

# Skip npm install if deps already present
python3 deploy.py --skip-install

# Tear down
python3 deploy.py --destroy
```

**CDK Outputs**: `ApiUrl`, `CloudFrontUrl`, `ImageBucketName`, `SubmissionsTableName`, `StateMachineArn`

---

## Summary

| Aspect                  | Details                                                      |
|-------------------------|--------------------------------------------------------------|
| **Purpose**             | Verify solar panel images for MNRE subsidy eligibility       |
| **Verification Steps**  | Quality -> Duplication -> Index -> Store                     |
| **AI Services**         | Rekognition + Titan Image Embeddings                         |
| **Time to Verification**| ~20–60 seconds                                               |
| **Scalability**         | Auto-scales to zero (no running costs when idle)             |
| **Auto-Expiry**         | 5 minutes for stale submissions                              |
| **Infrastructure**      | Fully serverless, single-command deploy/destroy             |
