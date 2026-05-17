import axios from 'axios';
import type { Submission, UploadResponse, ChequeUploadResponse } from '../types';

const API_BASE = import.meta.env.VITE_API_URL || '';

function parseBody<T>(data: unknown): T {
  if (typeof data === 'string') {
    return JSON.parse(data) as T;
  }
  const obj = data as Record<string, unknown>;
  if (obj.body !== undefined) {
    return typeof obj.body === 'string' ? JSON.parse(obj.body) as T : obj.body as T;
  }
  return data as T;
}

export async function requestUpload(userId: string, fileName: string, contentType: string): Promise<UploadResponse> {
  const { data } = await axios.post(`${API_BASE}/upload`, { userId, fileName, contentType });
  return parseBody<UploadResponse>(data);
}

export async function uploadFileToS3(uploadUrl: string, file: File): Promise<void> {
  await axios.put(uploadUrl, file, {
    headers: { 'Content-Type': file.type },
  });
}

export async function confirmUpload(submissionId: string): Promise<void> {
  await axios.post(`${API_BASE}/confirm`, { submissionId });
}

export async function getSubmissionStatus(submissionId: string): Promise<Submission> {
  const { data } = await axios.get(`${API_BASE}/status/${submissionId}`);
  return parseBody<Submission>(data);
}

export async function getUserSubmissions(userId: string): Promise<Submission[]> {
  const { data } = await axios.get(`${API_BASE}/submissions`, { params: { userId } });
  return parseBody<Submission[]>(data);
}

export async function requestChequeUpload(
  submissionId: string,
  fileName: string,
  contentType: string,
  expectedHolderName: string,
): Promise<ChequeUploadResponse> {
  const { data } = await axios.post(`${API_BASE}/cheque-upload`, {
    submissionId,
    fileName,
    contentType,
    expectedHolderName,
  });
  return parseBody<ChequeUploadResponse>(data);
}

export async function confirmChequeUpload(submissionId: string): Promise<void> {
  await axios.post(`${API_BASE}/cheque-confirm`, { submissionId });
}

export async function submitChequeReview(
  submissionId: string,
  decision: 'APPROVED' | 'DECLINED',
  reviewer: string,
  notes: string,
): Promise<void> {
  await axios.post(`${API_BASE}/cheque-review/${submissionId}`, { decision, reviewer, notes });
}
