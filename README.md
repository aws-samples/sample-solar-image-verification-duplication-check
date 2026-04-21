# MNRE Solar Panel Verification Portal

A serverless AWS application for the **Ministry of New and Renewable Energy (MNRE)** that verifies solar panel installation images submitted for government subsidy claims. The system uses a multi-step AI-powered verification pipeline to detect fraudulent, duplicate, or non-compliant submissions.

---

## Architecture

<img width="1621" height="1152" alt="mnre-solar-panel-architecture drawio" src="https://github.com/user-attachments/assets/788f0872-5df7-4768-964b-3e8e8731cd11" />

Step Functions Machine Orchestration:

<img width="1423" height="1600" alt="image" src="https://github.com/user-attachments/assets/6cca736e-b96c-47ca-a2a0-8881d162e6a7" />


---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite 6, Framer Motion |
| CDN | Amazon CloudFront |
| API | Amazon API Gateway (REST) |
| Compute | AWS Lambda (Python 3.12) |
| Orchestration | AWS Step Functions |
| Storage | Amazon S3, Amazon DynamoDB |
| AI/ML | Amazon Rekognition, Amazon Bedrock (Titan Embeddings, Claude Opus 4.7) |
| IaC | AWS CDK (TypeScript) |
| Region | ap-south-1 (Mumbai) |

---

## Project Structure

```
mnre-solar-panel-poc/
├── cdk/                          # AWS CDK infrastructure
│   ├── bin/app.ts                # CDK app entry point
│   └── lib/mnre-solar-panel-stack.ts  # Main stack definition
├── frontend/                     # React SPA
│   ├── src/
│   │   ├── api/client.ts         # API client (axios)
│   │   ├── components/
│   │   │   ├── ImageUpload.tsx       # Drag-and-drop upload
│   │   │   ├── SubmissionsList.tsx   # Submissions list with live updates
│   │   │   ├── SubmissionDetail.tsx  # Pipeline visualization
│   │   │   ├── DashboardStats.tsx    # Stats dashboard
│   │   │   ├── SolarScene.tsx        # Animated solar scene
│   │   │   ├── StatusBadge.tsx       # Animated status badges
│   │   │   └── ToastContainer.tsx    # Toast notifications
│   │   ├── App.tsx               # Main app with polling
│   │   ├── App.css               # Solar-themed styles
│   │   └── types.ts              # TypeScript interfaces
│   └── package.json
├── lambdas/                      # Lambda functions
│   ├── upload/                   # Pre-signed URL generation
│   ├── confirm_upload/           # S3 verification + Step Function start
│   ├── quality_check/            # Rekognition-based validation
│   ├── duplication_check/        # Titan embedding similarity
│   ├── custom_checks/            # Claude vision analysis
│   ├── index_image/              # Embedding storage for future lookups
│   ├── store_result/             # Final status persistence
│   ├── get_status/               # Status retrieval + auto-expiry
│   └── layers/common/            # Shared utilities (Pillow, helpers)
└── README.md
```

---

## Verification Pipeline

The Step Functions state machine executes these checks sequentially. If any check fails, the submission is immediately rejected and the result is stored.

### Step 1: Quality Check (Amazon Rekognition)

- Converts uploaded image to JPEG format using Pillow (handles PNG, WebP, BMP, TIFF, GIF)
- Calls `DetectLabels` to verify the image contains a solar panel (threshold: **70% confidence**)
- Calls `DetectModerationLabels` to flag inappropriate content
- Stores the converted JPEG back to S3 for downstream steps

### Step 2: Duplication Check (Titan Embeddings)

- Generates a 1024-dimensional image embedding using `amazon.titan-embed-image-v1`
- Computes cosine similarity against all previously indexed embeddings in DynamoDB
- Rejects if similarity exceeds **95%** (indicating a duplicate submission)
- Passes the embedding forward for indexing if the image is unique

### Step 3: Custom Checks (Claude Opus 4.7 Vision)

- Sends the image to Claude via Bedrock inference profile (`global.anthropic.claude-opus-4-7`)
- Analyzes:
  - **Solar panel tilt/inclination angle** — acceptable range: 20-40 degrees
  - **Image authenticity** — detects AI-generated, morphed, or digitally manipulated images
  - **Installation compliance** — verifies panels are properly mounted on a rooftop
- Falls back to Claude Sonnet if Opus is unavailable

### Step 4: Index Image

- Stores the image embedding in the Embeddings table (as DynamoDB `Decimal` values)
- Links embedding to submission ID and S3 key for future duplicate lookups

### Step 5: Store Result

- Writes final ACCEPTED/REJECTED status to the Submissions table
- Records completion timestamp and all check results

### Error Handling

- All pipeline steps have **Catch** blocks that route failures to a dedicated error handler
- Failed steps immediately mark the submission as REJECTED with the error details
- A **5-minute auto-expiry** mechanism marks stale PENDING/PROCESSING submissions as timed out

---

## Frontend Features

- **Drag-and-drop upload** with file preview (supports JPG, PNG, WebP, BMP, TIFF, GIF up to 15MB)
- **Real-time status polling** — 3s for active submission, 6s for submission list
- **Animated pipeline visualization** — shows progress through each verification step
- **Toast notifications** — alerts when submissions are accepted or rejected
- **Dashboard stats** — total, accepted, rejected, and processing counts
- **Solar-themed animations** — sun, solar panels, energy particles (Framer Motion)
- **Responsive design** with CSS variable-based theming

---

## Prerequisites

- Node.js 18+
- Python 3.12
- AWS CLI configured with `ap-south-1` region
- AWS CDK CLI (`npm install -g aws-cdk`)
- Bedrock model access enabled in your AWS account for:
  - `amazon.titan-embed-image-v1`
  - `anthropic.claude-opus-4-7-v1:0` (via inference profile `global.anthropic.claude-opus-4-7`)
  - `anthropic.claude-sonnet-4-20250514-v1:0` (via inference profile `apac.anthropic.claude-sonnet-4-20250514-v1:0`)

---

## Deployment

### First-time setup

```bash
# 1. Install dependencies
cd frontend && npm install && cd ..
cd cdk && npm install && cd ..

# 2. Bootstrap CDK (one-time per account/region)
cd cdk
npx cdk bootstrap aws://ACCOUNT_ID/ap-south-1

# 3. Build frontend (placeholder build for first deploy)
cd ../frontend
npm run build
cd ../cdk

# 4. Deploy infrastructure
npx cdk deploy
```

### Configure API URL and redeploy

```bash
# Copy the ApiUrl from CDK outputs
cd ../frontend
echo "VITE_API_URL=https://xxxxxxxxxx.execute-api.ap-south-1.amazonaws.com/prod/" > .env
npm run build

# Redeploy to update frontend with API URL
cd ../cdk
npx cdk deploy
```

### Subsequent deployments

```bash
cd frontend && npm run build && cd ../cdk && npx cdk deploy
```

---

## CDK Outputs

After deployment, these values are printed:

| Output | Description |
|--------|-------------|
| `ApiUrl` | REST API Gateway endpoint |
| `CloudFrontUrl` | Frontend application URL |
| `ImageBucketName` | S3 bucket for uploaded images |
| `SubmissionsTableName` | DynamoDB submissions table |
| `StateMachineArn` | Step Functions state machine ARN |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/upload` | Request a pre-signed S3 upload URL |
| `POST` | `/confirm` | Confirm upload and start verification pipeline |
| `GET` | `/status/{submissionId}` | Get single submission status |
| `GET` | `/submissions?userId=xxx` | Get all submissions for a user |

### Upload Flow

```
1. POST /upload { userId, fileName, contentType }
   → Returns { submissionId, uploadUrl }

2. PUT uploadUrl (binary file upload to S3)

3. POST /confirm { submissionId }
   → Verifies file exists in S3, starts Step Function
```

---

## DynamoDB Schema

### Submissions Table

| Attribute | Type | Description |
|-----------|------|-------------|
| `submissionId` (PK) | String | UUID |
| `userId` | String | User identifier |
| `status` | String | PENDING / PROCESSING / ACCEPTED / REJECTED |
| `s3Key` | String | S3 object key |
| `uploadedAt` | String | ISO timestamp |
| `completedAt` | String | ISO timestamp (when pipeline completes) |
| `rejectionReason` | String | Why the submission was rejected |
| `qualityCheckResult` | String (JSON) | Rekognition results |
| `duplicationCheckResult` | String (JSON) | Similarity scores |
| `customCheckResult` | String (JSON) | Claude analysis |

**GSI:** `userId-index` (partition: `userId`, sort: `uploadedAt`)

### Embeddings Table

| Attribute | Type | Description |
|-----------|------|-------------|
| `imageId` (PK) | String | UUID |
| `submissionId` | String | Linked submission |
| `s3Key` | String | S3 object key |
| `embedding` | List[Decimal] | 1024-dim vector |
| `createdAt` | String | ISO timestamp |

---

## Lambda Layer

The shared `common` layer includes:

- **`utils.py`** — Response builder, timestamp helper, JPEG conversion utility
- **`constants.py`** — Shared constants
- **Pillow (PIL)** — Image format conversion (compiled for `manylinux2014_x86_64`)

---

## Cleanup

```bash
cd cdk
npx cdk destroy
```

This removes all AWS resources including S3 buckets (with `RemovalPolicy.DESTROY` and `autoDeleteObjects`).
