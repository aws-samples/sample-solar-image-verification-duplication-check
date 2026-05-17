import { useState } from 'react';
import { motion } from 'framer-motion';
import type { ChequeValidationResult, PaymentStatus } from '../types';
import { submitChequeReview } from '../api/client';

interface ChequeValidationPanelProps {
  submissionId: string;
  paymentStatus: PaymentStatus;
  result?: ChequeValidationResult;
  expectedHolderName?: string;
  reviewedBy?: string;
  reviewNotes?: string;
  onReviewSubmitted: () => void;
}

function statusLabel(s: PaymentStatus): string {
  return {
    PENDING_CHEQUE: 'Awaiting cheque',
    VALIDATING: 'Validating',
    APPROVED: 'Approved',
    DECLINED: 'Declined',
    NEEDS_REVIEW: 'Needs review',
  }[s];
}

function statusColor(s: PaymentStatus): string {
  return {
    PENDING_CHEQUE: '#6b7280',
    VALIDATING: '#0ea5e9',
    APPROVED: '#16a34a',
    DECLINED: '#dc2626',
    NEEDS_REVIEW: '#d97706',
  }[s];
}

function Field({ label, value, mono }: { label: string; value: string | number | boolean | undefined; mono?: boolean }) {
  let display: string;
  if (typeof value === 'boolean') display = value ? 'Yes' : 'No';
  else if (value === undefined || value === null || value === '') display = '—';
  else display = String(value);
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', padding: '0.25rem 0' }}>
      <span style={{ color: '#6b7280', fontSize: '0.78rem' }}>{label}</span>
      <span style={{ fontSize: '0.82rem', fontFamily: mono ? 'ui-monospace, monospace' : undefined }}>{display}</span>
    </div>
  );
}

export default function ChequeValidationPanel({
  submissionId,
  paymentStatus,
  result,
  expectedHolderName,
  reviewedBy,
  reviewNotes,
  onReviewSubmitted,
}: ChequeValidationPanelProps) {
  const [reviewer, setReviewer] = useState('officer');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleReview = async (decision: 'APPROVED' | 'DECLINED') => {
    setSubmitting(true);
    setError(null);
    try {
      await submitChequeReview(submissionId, decision, reviewer.trim() || 'officer', notes.trim());
      onReviewSubmitted();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Review submission failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      style={{ marginTop: '1rem', padding: '0.85rem', border: '1px solid #e5e7eb', borderRadius: 8 }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem' }}>
        <span className="material-symbols-rounded" style={{ fontSize: 18 }}>payments</span>
        <strong>Fund Release</strong>
        <span
          style={{
            marginLeft: 'auto',
            padding: '0.15rem 0.55rem',
            borderRadius: 999,
            fontSize: '0.72rem',
            fontWeight: 600,
            color: 'white',
            background: statusColor(paymentStatus),
          }}
        >
          {statusLabel(paymentStatus)}
        </span>
      </div>

      {paymentStatus === 'VALIDATING' && (
        <p style={{ fontSize: '0.82rem', color: '#6b7280' }}>
          Running cheque OCR (Claude Opus 4.7), verifying IFSC via Razorpay, and evaluating decision...
        </p>
      )}

      {result && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 1rem', marginTop: '0.4rem' }}>
          <div>
            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#9ca3af', marginBottom: '0.2rem' }}>
              From cheque (OCR)
            </div>
            <Field label="IFSC" value={result.ifsc} mono />
            <Field label="Account #" value={result.accountNumber} mono />
            <Field label="Holder name" value={result.holderName} />
            <Field label="Bank" value={result.bankName} />
            <Field label="Branch" value={result.branch} />
            <Field label="MICR" value={result.micr} mono />
            <Field label="'CANCELLED' marking" value={result.hasCancelledStamp} />
            <Field label="Signature" value={result.hasSignature} />
            <Field label="OCR confidence" value={result.ocrConfidence?.toFixed(2)} />
          </div>

          <div>
            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: '#9ca3af', marginBottom: '0.2rem' }}>
              From IFSC API (Razorpay)
            </div>
            <Field label="Verified" value={result.ifscVerified} />
            {result.ifscError && <Field label="Error" value={result.ifscError} />}
            <Field label="Bank" value={result.ifscApiBank} />
            <Field label="Branch" value={result.ifscApiBranch} />
            <Field label="Address" value={result.ifscApiAddress} />

            <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', textTransform: 'uppercase', color: '#9ca3af', marginBottom: '0.2rem' }}>
              Match scores
            </div>
            <Field label="Bank-name match" value={result.bankMatchScore?.toFixed(2)} />
            <Field label="Holder-name match" value={result.nameMatchScore?.toFixed(2)} />
            {expectedHolderName && <Field label="Expected holder" value={expectedHolderName} />}
          </div>
        </div>
      )}

      {result && (result.hardFails?.length > 0 || result.softFails?.length > 0) && (
        <div style={{ marginTop: '0.6rem' }}>
          {result.hardFails?.map((m) => (
            <div key={m} style={{ fontSize: '0.78rem', color: '#dc2626', marginBottom: '0.2rem' }}>
              <span className="material-symbols-rounded" style={{ fontSize: 14, verticalAlign: 'middle' }}>cancel</span> {m}
            </div>
          ))}
          {result.softFails?.map((m) => (
            <div key={m} style={{ fontSize: '0.78rem', color: '#d97706', marginBottom: '0.2rem' }}>
              <span className="material-symbols-rounded" style={{ fontSize: 14, verticalAlign: 'middle' }}>warning</span> {m}
            </div>
          ))}
        </div>
      )}

      {paymentStatus === 'NEEDS_REVIEW' && (
        <div style={{ marginTop: '0.7rem', paddingTop: '0.7rem', borderTop: '1px solid #f3f4f6' }}>
          <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.4rem' }}>Manual review</div>
          <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '0.4rem' }}>
            <input
              type="text"
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              placeholder="Reviewer name"
              style={{ flex: 1, padding: '0.4rem 0.55rem', fontSize: '0.82rem', borderRadius: 6, border: '1px solid #d1d5db' }}
            />
          </div>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Notes (optional)"
            rows={2}
            style={{ width: '100%', padding: '0.4rem 0.55rem', fontSize: '0.82rem', borderRadius: 6, border: '1px solid #d1d5db', resize: 'vertical' }}
          />
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
            <button
              className="btn btn-primary"
              onClick={() => handleReview('APPROVED')}
              disabled={submitting}
              style={{ flex: 1 }}
            >
              Approve fund release
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => handleReview('DECLINED')}
              disabled={submitting}
              style={{ flex: 1 }}
            >
              Decline
            </button>
          </div>
          {error && <p style={{ color: '#dc2626', fontSize: '0.78rem', marginTop: '0.4rem' }}>{error}</p>}
        </div>
      )}

      {(paymentStatus === 'APPROVED' || paymentStatus === 'DECLINED') && reviewedBy && (
        <div style={{ marginTop: '0.6rem', paddingTop: '0.5rem', borderTop: '1px solid #f3f4f6', fontSize: '0.78rem', color: '#6b7280' }}>
          Reviewed by <strong>{reviewedBy}</strong>{reviewNotes ? ` — ${reviewNotes}` : ''}
        </div>
      )}
    </motion.div>
  );
}
