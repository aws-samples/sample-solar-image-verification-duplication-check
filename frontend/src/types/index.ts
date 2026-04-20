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
  reason?: string;
}

export interface UploadResponse {
  submissionId: string;
  uploadUrl: string;
}
