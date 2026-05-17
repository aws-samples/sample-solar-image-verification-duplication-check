export type PaymentStatus = 'PENDING_CHEQUE' | 'VALIDATING' | 'APPROVED' | 'DECLINED' | 'NEEDS_REVIEW';

export interface Submission {
  submissionId: string;
  userId: string;
  status: 'PENDING' | 'PROCESSING' | 'ACCEPTED' | 'REJECTED';
  uploadedAt: string;
  completedAt?: string;
  rejectionReason?: string;
  qualityCheckResult?: QualityCheckResult;
  duplicationCheckResult?: DuplicationCheckResult;
  customCheckResult?: CustomCheckResult;
  paymentStatus?: PaymentStatus;
  expectedHolderName?: string;
  chequeUploadedAt?: string;
  paymentDecidedAt?: string;
  paymentReviewedBy?: string;
  paymentReviewNotes?: string;
  chequeValidationResult?: ChequeValidationResult;
}

export interface ChequeValidationResult {
  ifsc: string;
  accountNumber: string;
  holderName: string;
  bankName: string;
  branch: string;
  micr: string;
  hasCancelledStamp: boolean;
  hasSignature: boolean;
  ifscApiBank: string;
  ifscApiBranch: string;
  ifscApiAddress: string;
  ifscVerified: boolean;
  ifscError?: string;
  bankMatchScore: number;
  nameMatchScore: number;
  ocrConfidence: number;
  hardFails: string[];
  softFails: string[];
}

export interface ChequeUploadResponse {
  submissionId: string;
  uploadUrl: string;
  chequeS3Key: string;
}

export interface QualityCheckResult {
  solarPanelConfidence: number;
  labels: string[];
  reason?: string;
}

export interface DuplicationCheckResult {
  maxSimilarity: number;
  matchedImageId?: string;
}

export interface CustomCheckResult {
  inclination: {
    estimated_angle: number;
    acceptable: boolean;
    confidence: string;
    notes: string;
  };
  authenticity: {
    is_authentic: boolean;
    confidence: string;
    manipulation_signs: string[];
    notes: string;
  };
  watermark: {
    has_watermark: boolean;
    is_internet_sourced: boolean;
    confidence: string;
    detected_marks: string[];
    notes: string;
  };
  reason?: string;
}

export interface UploadResponse {
  submissionId: string;
  uploadUrl: string;
}
