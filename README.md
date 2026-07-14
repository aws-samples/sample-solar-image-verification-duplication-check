# MNRE Solar Panel Verification Portal

A serverless AWS application for the **Ministry of New and Renewable Energy (MNRE)** that verifies solar panel installation images submitted for government subsidy claims. This POC runs a two-check AI verification pipeline — solar panel detection via Amazon Rekognition, followed by a duplicate-image check via Amazon Titan image embeddings.

---

## Architecture
<img width="1621" height="1152" alt="mnre-solar-panel-architecture drawio" src="https://github.com/user-attachments/assets/788f0872-5df7-4768-964b-3e8e8731cd11" />

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
| AI/ML | Amazon Rekognition, Amazon Bedrock (Titan Image Embeddings) |
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
│   │   │   ├── ImageUpload.tsx           # Drag-and-drop upload
│   │   │   ├── SubmissionsList.tsx       # Submissions list with live updates
│   │   │   ├── SubmissionDetail.tsx      # Pipeline visualization
│   │   │   ├── DashboardStats.tsx        # Stats dashboard
│   │   │   ├── SolarScene.tsx            # Animated solar scene
│   │   │   ├── StatusBadge.tsx           # Animated status badges
│   │   │   └── ToastContainer.tsx        # Toast notifications
│   │   ├── App.tsx               # Main app with polling
│   │   ├── App.css               # Solar-themed styles
│   │   └── types/index.ts        # TypeScript interfaces
│   └── package.json
├── lambdas/                      # Lambda functions
│   ├── upload/                   # Pre-signed URL generation (image)
│   ├── confirm_upload/           # S3 verification + image Step Function start
│   ├── quality_check/            # Rekognition-based validation
│   ├── duplication_check/        # Titan embedding similarity
│   ├── index_image/              # Embedding storage for future lookups
│   ├── store_result/             # Final image status persistence
│   ├── get_status/               # Status retrieval + auto-expiry
│   └── layers/common/            # Shared utilities (Pillow, helpers)
├── deploy.py                     # End-to-end deploy script (wraps CDK)
├── mnre-solar-panel-architecture.drawio       # Image pipeline architecture
└── README.md
```

---

## Verification Pipeline — Deep Dive

The Step Functions state machine executes two checks sequentially. If either check fails, the submission is immediately rejected and the result is stored.

```
Image Upload
     │
     ▼
┌─────────────────────────┐
│  Step 1: Quality Check  │  ← Is this actually a solar panel?
│  (Amazon Rekognition)   │
└───────────┬─────────────┘
            │ Pass (≥70% confidence)
            ▼
┌──────────────────────────┐
│ Step 2: Duplication Check│  ← Has this exact image been submitted before?
│ (Titan Image Embeddings) │
└───────────┬──────────────┘
            │ Pass (<95% similarity)
            ▼
┌──────────────────────────┐
│  Step 3: Index Image     │  ← Store embedding for future duplicate detection
│  (DynamoDB)              │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│  Step 4: Store Result    │  ← Write ACCEPTED to DynamoDB
│  (DynamoDB)              │
└──────────────────────────┘
```

---

### Step 1: Quality Check (Amazon Rekognition)

**Lambda:** `lambdas/quality_check/handler.py`

**Purpose:** Verify that the uploaded image actually contains a solar panel installation, and flag inappropriate content.

**How it works:**

1. **Image conversion** — The uploaded image (which may be PNG, WebP, BMP, TIFF, or GIF) is converted to JPEG using Pillow. This normalized JPEG is saved back to S3 as `{original_name}_converted.jpg` and used by all downstream steps.

2. **Label detection** — Calls Rekognition `DetectLabels` and searches for solar-panel-related labels including: `Solar Panel`, `Solar Energy`, `Solar Power`, `Electrical Device`, `Power Supply`. It checks both direct label names and their parent categories. The highest confidence score across all matching labels becomes the `solarPanelConfidence`.

3. **Confidence threshold** — The image passes if `solarPanelConfidence >= 70%`. Below this, the image is rejected with the message: *"Solar panel not detected (confidence: X%)"*.

4. **Content moderation** — Calls Rekognition `DetectModerationLabels`. If any moderation labels are found, the submission is rejected regardless of solar panel confidence.

**Output example:**
```json
{
  "passed": true,
  "solarPanelConfidence": 96.5,
  "labels": ["Electrical Device", "Solar Panels", "Architecture", "Building"],
  "reason": null
}
```

---

### Step 2: Duplication Check (Titan Image Embeddings)

**Lambda:** `lambdas/duplication_check/handler.py`

**Purpose:** Detect if the same (or near-identical) image has been submitted before, preventing the same installation photo from being used for multiple subsidy claims.

**How vector embeddings work:**

An image embedding is a mathematical representation of a photo's visual content as a list of 1,024 floating-point numbers (a vector). Amazon Titan Embed Image v1 takes an image and outputs this fixed-length vector. Visually similar images produce vectors that point in nearly the same direction in 1,024-dimensional space.

```
Photo of rooftop solar panels    →  [0.0234, -0.1567, 0.0891, 0.2341, ...]  (1024 numbers)
Same photo slightly cropped      →  [0.0229, -0.1571, 0.0887, 0.2338, ...]  (very similar!)
Photo of a cat                   →  [0.8912, 0.0034, -0.4521, 0.1102, ...]  (totally different)
```

**How the duplication check works:**

1. **Generate embedding** — The uploaded image is read from S3, base64-encoded, and sent to `amazon.titan-embed-image-v1` via Bedrock. The model returns a 1,024-dimensional vector.

2. **Scan existing embeddings** — All previously stored embeddings are loaded from the Embeddings DynamoDB table using a full table scan (with pagination).

3. **Cosine similarity comparison** — The new embedding is compared against every stored embedding:

   ```
   cosine_similarity(A, B) = (A · B) / (|A| × |B|)
   ```

4. **Threshold check** — If the maximum similarity exceeds **0.95 (95%)**, the image is flagged as a duplicate.

5. **Pass embedding forward** — The computed embedding is included in the output so that Step 3 (Index Image) can store it without re-computing.

**Output example:**
```json
{
  "passed": true,
  "maxSimilarity": 0.498,
  "matchedImageId": null,
  "embedding": [0.0234, -0.1567, ...]
}
```

**Scaling note:** The current implementation performs a full DynamoDB scan and in-memory comparison for every check. This works for POC-scale (hundreds of images) but would need a vector database (e.g., Aurora PostgreSQL with pgvector, or OpenSearch) for production-scale workloads.

---

### Step 3: Index Image

**Lambda:** `lambdas/index_image/handler.py`

**Purpose:** Store the image's vector embedding in DynamoDB so future submissions can be checked for duplicates against it.

Retrieves the embedding from the duplication check result, generates a UUID `imageId`, converts each float to `Decimal`, and stores the record linking `imageId`, `submissionId`, `s3Key`, the embedding, and a timestamp. This step only executes for **accepted** submissions.

---

### Step 4: Store Result

**Lambda:** `lambdas/store_result/handler.py`

**Purpose:** Write the final ACCEPTED or REJECTED status to the Submissions DynamoDB table, along with all check results and a completion timestamp. Also invoked by the error-handling paths — if any pipeline step throws, the Step Functions Catch block routes here to record the failure.

---

### Error Handling & Auto-Expiry

- **Step-level error handling:** Every pipeline step has a `Catch` block that routes unhandled exceptions to a `StoreErrorResult` task marking the submission REJECTED with error details.
- **Rejection branching:** After each check, a `Choice` state short-circuits to a reject path if the check failed, skipping subsequent checks.
- **Auto-expiry:** The Get Status Lambda marks submissions stuck in PENDING/PROCESSING for more than 5 minutes as REJECTED with a timeout reason.

---

## Frontend Features

- **Drag-and-drop upload** with file preview (supports JPG, PNG, WebP, BMP, TIFF, GIF up to 15MB)
- **Real-time status polling** — 3s for active submission, 6s for submission list
- **Animated pipeline visualization** — shows progress through each verification step with pass/fail indicators
- **Toast notifications** — alerts when submissions are accepted or rejected
- **Dashboard stats** — total, accepted, rejected, and processing counts
- **Solar-themed animations** — sun, solar panels, energy particles (Framer Motion)

---

## Prerequisites

- Node.js 18+
- Python 3.12
- AWS CLI configured with `ap-south-1` region
- AWS CDK CLI (`npm install -g aws-cdk`)
- Bedrock model access enabled in your AWS account for:
  - `amazon.titan-embed-image-v1` (image embeddings for duplication check)

---

## Deployment

### One-command deploy (recommended)

```bash
python3 deploy.py
```

This installs dependencies, bootstraps CDK, builds the frontend, deploys the stack, wires the API URL into `frontend/.env`, then rebuilds and redeploys so CloudFront serves the API-connected build.

Options:

```bash
python3 deploy.py --skip-install   # deps already installed
python3 deploy.py --destroy        # tear everything down
```

### Manual deploy (CDK directly)

```bash
# 1. Install dependencies
cd frontend && npm install && cd ..
cd cdk && npm install && cd ..

# 2. Bootstrap CDK (one-time per account/region)
cd cdk && npx cdk bootstrap aws://ACCOUNT_ID/ap-south-1

# 3. Build frontend + deploy
cd ../frontend && npm run build
cd ../cdk && npx cdk deploy

# 4. Wire API URL and redeploy
cd ../frontend
echo "VITE_API_URL=https://xxxxxxxxxx.execute-api.ap-south-1.amazonaws.com/prod/" > .env
npm run build
cd ../cdk && npx cdk deploy
```

---

## CDK Outputs

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

2. PUT uploadUrl (binary file upload directly to S3 using pre-signed URL)

3. POST /confirm { submissionId }
   → Verifies file exists in S3, starts Step Functions state machine
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
| `qualityCheckResult` | String (JSON) | Rekognition label detection results |
| `duplicationCheckResult` | String (JSON) | Similarity scores and matched image ID |

**GSI:** `userId-index` (partition: `userId`, sort: `uploadedAt`)

### Embeddings Table

| Attribute | Type | Description |
|-----------|------|-------------|
| `imageId` (PK) | String | UUID |
| `submissionId` | String | Linked submission |
| `s3Key` | String | S3 object key |
| `embedding` | List[Decimal] | 1,024-dimensional Titan image embedding vector |
| `createdAt` | String | ISO timestamp |

---

## Lambda Layer

The shared `common` layer (`lambdas/layers/common/python/`) includes:

- **`utils.py`** — Response builder, cosine similarity function, timestamp helper, JPEG conversion utility
- **`constants.py`** — Shared constants (similarity threshold 0.95, min solar panel confidence 70%, solar panel label list, status values)
- **Pillow (PIL)** — Image format conversion (compiled for `manylinux2014_x86_64`)

---

## Cleanup

```bash
python3 deploy.py --destroy
# or: cd cdk && npx cdk destroy
```

This removes all AWS resources including S3 buckets (with `RemovalPolicy.DESTROY` and `autoDeleteObjects`).
