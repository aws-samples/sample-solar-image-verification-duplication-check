export interface Submission {
  submissionId: string;
  userId: string;
  status: 'PENDING' | 'PROCESSING' | 'ACCEPTED' | 'REJECTED';
  uploadedAt: string;
  completedAt?: string;
  rejectionReason?: string;
  qualityCheckResult?: QualityCheckResult;
  duplicationCheckResult?: DuplicationCheckResult;
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

export interface UploadResponse {
  submissionId: string;
  uploadUrl: string;
}
