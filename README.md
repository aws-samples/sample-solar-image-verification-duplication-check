# MNRE Solar Panel Verification Portal

A serverless AWS application for the **Ministry of New and Renewable Energy (MNRE)** that verifies solar panel installation images submitted for government subsidy claims. The system uses a multi-step AI-powered verification pipeline to detect fraudulent, duplicate, or non-compliant submissions.

---

## Architecture
<img width="1621" height="1152" alt="mnre-solar-panel-architecture drawio" src="https://github.com/user-attachments/assets/788f0872-5df7-4768-964b-3e8e8731cd11" />

## Step Functions Machine Orchestration
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
| AI/ML | Amazon Rekognition, Amazon Bedrock (Titan Embeddings, Google Gemma 3 12B IT) |
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
│   │   └── types/index.ts        # TypeScript interfaces
│   └── package.json
├── lambdas/                      # Lambda functions
│   ├── upload/                   # Pre-signed URL generation
│   ├── confirm_upload/           # S3 verification + Step Function start
│   ├── quality_check/            # Rekognition-based validation
│   ├── duplication_check/        # Titan embedding similarity
│   ├── custom_checks/            # Gemma 3 12B IT vision analysis
│   ├── index_image/              # Embedding storage for future lookups
│   ├── store_result/             # Final status persistence
│   ├── get_status/               # Status retrieval + auto-expiry
│   └── layers/common/            # Shared utilities (Pillow, helpers)
└── README.md
```

---

## Verification Pipeline — Deep Dive

The Step Functions state machine executes these checks sequentially. If any check fails, the submission is immediately rejected and the result is stored. The pipeline processes each submission through 5 stages:

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
│  Step 3: Custom Checks   │  ← Is the tilt correct? Is the image tampered/watermarked?
│  (Gemma 3 12B IT Vision) │
└───────────┬──────────────┘
            │ Pass (all 3 sub-checks)
            ▼
┌──────────────────────────┐
│  Step 4: Index Image     │  ← Store embedding for future duplicate detection
│  (DynamoDB)              │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│  Step 5: Store Result    │  ← Write ACCEPTED to DynamoDB
│  (DynamoDB)              │
└──────────────────────────┘
```

---

### Step 1: Quality Check (Amazon Rekognition)

**Lambda:** `lambdas/quality_check/handler.py`

**Purpose:** Verify that the uploaded image actually contains a solar panel installation, and flag inappropriate content.

**How it works:**

1. **Image conversion** — The uploaded image (which may be PNG, WebP, BMP, TIFF, or GIF) is converted to JPEG using Pillow. This normalized JPEG is saved back to S3 as `{original_name}_converted.jpg` and used by all downstream steps. This ensures consistent format handling across the pipeline.

2. **Label detection** — Calls Rekognition `DetectLabels` with up to 25 labels at a minimum 50% confidence. The function searches for solar-panel-related labels including: `Solar Panel`, `Solar Energy`, `Solar Power`, `Electrical Device`, `Power Supply`. It checks both direct label names and their parent categories (e.g., if Rekognition returns `Monocrystalline Panel` with parent `Solar Panel`, it counts). The highest confidence score across all matching labels becomes the `solarPanelConfidence`.

3. **Confidence threshold** — The image passes if `solarPanelConfidence >= 70%`. Below this, the image is rejected with the message: *"Solar panel not detected (confidence: X%)"*.

4. **Content moderation** — Calls Rekognition `DetectModerationLabels` at 75% confidence. If any moderation labels are found (violence, explicit content, etc.), the submission is rejected regardless of solar panel confidence.

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

An image embedding is a mathematical representation of a photo's visual content as a list of 1,024 floating-point numbers (a vector). Amazon Titan Embed Image v1 is a neural network that takes an image as input and outputs this fixed-length vector.

The key property: **visually similar images produce vectors that point in nearly the same direction in 1,024-dimensional space**. Two photos of the same building from the same angle will have nearly identical vectors, while completely different photos will have vectors pointing in very different directions.

```
Photo of rooftop solar panels    →  [0.0234, -0.1567, 0.0891, 0.2341, ...]  (1024 numbers)
Same photo slightly cropped      →  [0.0229, -0.1571, 0.0887, 0.2338, ...]  (very similar!)
Photo of a cat                   →  [0.8912, 0.0034, -0.4521, 0.1102, ...]  (totally different)
```

**How the duplication check works:**

1. **Generate embedding** — The uploaded image is read from S3, base64-encoded, and sent to `amazon.titan-embed-image-v1` via Bedrock. The model returns a 1,024-dimensional vector.

2. **Scan existing embeddings** — All previously stored embeddings are loaded from the Embeddings DynamoDB table using a full table scan (with pagination for large datasets).

3. **Cosine similarity comparison** — The new embedding is compared against every stored embedding using cosine similarity:

   ```
   cosine_similarity(A, B) = (A · B) / (|A| × |B|)
   ```

   This measures the cosine of the angle between two vectors. The result ranges from -1 to 1, where 1 means identical direction (identical images) and 0 means completely unrelated.

4. **Threshold check** — If the maximum similarity across all stored embeddings exceeds **0.95 (95%)**, the image is flagged as a duplicate. The matched image ID is returned for reference.

5. **Pass embedding forward** — The computed embedding is included in the output so that Step 4 (Index Image) can store it without re-computing.

**Output example:**
```json
{
  "passed": true,
  "maxSimilarity": 0.498,
  "matchedImageId": null,
  "embedding": [0.0234, -0.1567, ...]
}
```

**Scaling note:** The current implementation performs a full DynamoDB scan and in-memory comparison for every check. This works for POC-scale (hundreds of images) but would need to be replaced with a vector database (e.g., Aurora PostgreSQL with pgvector, or OpenSearch) for production-scale workloads with thousands of embeddings.

---

### Step 3: Custom Checks (Gemma 3 12B IT Vision)

**Lambda:** `lambdas/custom_checks/handler.py`

**Purpose:** Perform intelligent visual analysis that goes beyond what Rekognition can do — checking the physical installation angle, detecting image tampering, and identifying watermarks/internet-sourced images.

**Model:** Google Gemma 3 12B IT, invoked via the Amazon Bedrock Converse API (`bedrock.converse()`). The Converse API provides a unified request/response format across all Bedrock models, so swapping the model only requires changing the model ID.

**How it works:**

The Lambda reads the image from S3, passes it as raw bytes to Gemma along with a detailed analysis prompt, and parses the structured JSON response. The model performs three sub-checks:

#### Sub-check 3a: Inclination (Panel Tilt Angle)

The model estimates the tilt angle of the solar panels from horizontal by analyzing the perspective and geometry in the image. Per MNRE guidelines, the optimal tilt for India is approximately 30 degrees, with an acceptable range of **20-40 degrees**.

- **Pass:** Estimated angle is between 20° and 40°
- **Fail:** Angle is outside this range (e.g., panels are flat or too steep)

#### Sub-check 3b: Image Authenticity

The model examines the image for signs of digital manipulation:
- Inconsistent lighting or shadows
- Warping or distortion artifacts
- Clone stamping patterns
- Unnatural edge boundaries around the solar panels
- Compression artifacts inconsistent with a single capture
- Signs of image compositing or splicing

- **Pass:** `is_authentic = true`
- **Fail:** `is_authentic = false` with a list of `manipulation_signs`

#### Sub-check 3c: Watermark & Internet Sourcing

The model checks for concrete visual evidence that the image was downloaded from the internet rather than photographed at an actual installation site:
- Visible watermark text, logos, or semi-transparent stamps
- Stock photo agency identifiers (Getty, Shutterstock, iStock, Adobe Stock text/logos)
- Visible URL or website text embedded in the image
- Screenshot artifacts (browser chrome, address bars, UI elements)

This check is intentionally strict about what counts as evidence — high image quality, good lighting, or professional composition alone are **not** flagged. Only explicit visual proof of watermarks or internet sourcing triggers a failure.

- **Pass:** `has_watermark = false` AND `is_internet_sourced = false`
- **Fail:** Either flag is `true`

**The overall custom check passes only if all three sub-checks pass.**

**Output example:**
```json
{
  "passed": true,
  "inclination": {
    "estimated_angle": 35,
    "acceptable": true,
    "confidence": "high",
    "notes": "Panel tilt is approximately 35 degrees, within the MNRE acceptable range."
  },
  "authenticity": {
    "is_authentic": true,
    "confidence": "high",
    "manipulation_signs": [],
    "notes": "Image shows consistent lighting, natural shadows, and no signs of manipulation."
  },
  "watermark": {
    "has_watermark": false,
    "is_internet_sourced": false,
    "confidence": "high",
    "detected_marks": [],
    "notes": "No watermarks, stock agency marks, or internet sourcing indicators found."
  },
  "reason": null
}
```

---

### Step 4: Index Image

**Lambda:** `lambdas/index_image/handler.py`

**Purpose:** Store the image's vector embedding in DynamoDB so future submissions can be checked for duplicates against it.

**How it works:**

1. Retrieves the embedding (1,024 floats) from the duplication check result that was passed through the pipeline state.
2. Generates a new UUID as the `imageId`.
3. Converts each float to `Decimal` (DynamoDB doesn't support float types natively).
4. Stores the record in the Embeddings table linking `imageId`, `submissionId`, `s3Key`, the embedding vector, and a timestamp.

This step only executes for **accepted** submissions — rejected images are not indexed, so they won't affect future duplicate comparisons.

---

### Step 5: Store Result

**Lambda:** `lambdas/store_result/handler.py`

**Purpose:** Write the final ACCEPTED or REJECTED status to the Submissions DynamoDB table, along with all check results and a completion timestamp.

This Lambda is also invoked by the error-handling paths — if any pipeline step throws an exception, the Step Functions Catch block routes to this function to record the failure.

---

### Error Handling & Auto-Expiry

- **Step-level error handling:** Every pipeline step (Quality Check, Duplication Check, Custom Checks, Index Image) has a `Catch` block in the Step Functions definition. If a Lambda throws an unhandled exception, the error is caught and routed to a dedicated `StoreErrorResult` task that marks the submission as REJECTED with the error details.

- **Rejection branching:** After each check, a `Choice` state evaluates whether the check passed. If it failed, the pipeline short-circuits to a `RejectXxx → StoreRejectXxx` path, skipping all subsequent checks.

- **Auto-expiry:** The Get Status Lambda includes a 5-minute timeout mechanism. If a submission has been in PENDING or PROCESSING status for more than 5 minutes, it's automatically marked as REJECTED with a timeout reason. This prevents zombie submissions from appearing stuck in the UI.

---

## Frontend Features

- **Drag-and-drop upload** with file preview (supports JPG, PNG, WebP, BMP, TIFF, GIF up to 15MB)
- **Real-time status polling** — 3s for active submission, 6s for submission list
- **Animated pipeline visualization** — shows progress through each verification step with pass/fail indicators
- **Watermark & Internet Sourcing display** — shows watermark detection status and internet-sourced verdict
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
  - `amazon.titan-embed-image-v1` (image embeddings for duplication check)
  - `google.gemma-3-12b-it` (vision model for custom checks)

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
| `customCheckResult` | String (JSON) | Gemma vision analysis (inclination, authenticity, watermark) |

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
- **`constants.py`** — Shared constants (similarity threshold 0.95, min solar panel confidence 70%, inclination range 20-40°, solar panel label list)
- **Pillow (PIL)** — Image format conversion (compiled for `manylinux2014_x86_64`)

---

## Cleanup

```bash
cd cdk
npx cdk destroy
```

This removes all AWS resources including S3 buckets (with `RemovalPolicy.DESTROY` and `autoDeleteObjects`).
