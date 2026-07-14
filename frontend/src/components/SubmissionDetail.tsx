import { motion, AnimatePresence } from 'framer-motion';
import type { Submission } from '../types';
import StatusBadge from './StatusBadge';

interface SubmissionDetailProps {
  submission: Submission;
}

type StepStatus = 'pass' | 'fail' | 'active' | 'pending';

function getStepStatus(result: { passed?: boolean } | undefined, previousPassed: boolean, isProcessing: boolean): StepStatus {
  if (!result) {
    if (!previousPassed) return 'pending';
    return isProcessing ? 'active' : 'pending';
  }
  return result.passed !== false ? 'pass' : 'fail';
}

function PipelineDot({ status, index }: { status: StepStatus; index: number }) {
  const icon = { pass: 'check', fail: 'close', active: 'more_horiz', pending: '' }[status];
  return (
    <motion.div
      className={`pipeline-dot ${status}`}
      initial={{ scale: 0 }}
      animate={{ scale: 1 }}
      transition={{ delay: index * 0.1, type: 'spring', stiffness: 400 }}
    >
      {icon ? <span className="material-symbols-rounded">{icon}</span> : null}
    </motion.div>
  );
}

function ConnectorLine({ status }: { status: StepStatus }) {
  const cls = status === 'pass' ? 'done' : status === 'active' ? 'active' : 'pending';
  return <div className={`pipeline-connector ${cls}`} />;
}

function PipelineStep({ status, index, title, subtitle, children }: {
  status: StepStatus; index: number; title: string; subtitle: string; children?: React.ReactNode;
}) {
  return (
    <motion.div
      className="pipeline-step"
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.08, duration: 0.3 }}
    >
      <div className="pipeline-track">
        <PipelineDot status={status} index={index} />
        <ConnectorLine status={status} />
      </div>
      <div className="pipeline-content">
        <div className="pipeline-title">
          {title}
          <span className="pipeline-subtitle">{subtitle}</span>
        </div>
        <AnimatePresence>
          {children && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.25 }}
            >
              {children}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

export default function SubmissionDetail({ submission }: SubmissionDetailProps) {
  const { qualityCheckResult, duplicationCheckResult } = submission;
  const isProcessing = submission.status === 'PROCESSING' || submission.status === 'PENDING';

  const qualityStatus = getStepStatus(
    qualityCheckResult ? { passed: qualityCheckResult.solarPanelConfidence >= 70 } : undefined, true, isProcessing,
  );
  const qualityPassed = qualityCheckResult ? qualityCheckResult.solarPanelConfidence >= 70 : false;

  const duplicationStatus = getStepStatus(
    duplicationCheckResult ? { passed: duplicationCheckResult.maxSimilarity < 0.95 } : undefined, qualityPassed, isProcessing,
  );
  const duplicationPassed = duplicationCheckResult ? duplicationCheckResult.maxSimilarity < 0.95 : false;

  const allPassed = qualityPassed && duplicationPassed;

  const indexStatus: StepStatus = allPassed ? 'pass' : 'pending';
  const finalStatus: StepStatus = submission.status === 'ACCEPTED' ? 'pass' : submission.status === 'REJECTED' ? 'fail' : 'pending';

  return (
    <div className="detail-panel">
      <motion.div className="detail-header" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <div className="detail-meta">
          <div className="detail-id">{submission.submissionId}</div>
          <div className="detail-time">Uploaded {new Date(submission.uploadedAt).toLocaleString()}</div>
          {submission.completedAt && (
            <div className="detail-time">Completed {new Date(submission.completedAt).toLocaleString()}</div>
          )}
        </div>
        <StatusBadge status={submission.status} />
      </motion.div>

      <AnimatePresence>
        {submission.rejectionReason && (
          <motion.div
            className="rejection-banner"
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
          >
            <span className="material-symbols-rounded">warning</span>
            <div>{submission.rejectionReason}</div>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="pipeline">
        <PipelineStep status={qualityStatus} index={0} title="Quality Check" subtitle="AWS Rekognition">
          {qualityCheckResult ? (
            <div className="pipeline-detail">
              <p>
                Solar Panel Confidence:{' '}
                <span className={`metric-value ${qualityCheckResult.solarPanelConfidence >= 70 ? 'pass' : 'fail'}`}>
                  {qualityCheckResult.solarPanelConfidence.toFixed(1)}%
                </span>
              </p>
              <div className="confidence-bar">
                <motion.div
                  className={`confidence-fill ${qualityCheckResult.solarPanelConfidence >= 70 ? 'pass' : 'fail'}`}
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(qualityCheckResult.solarPanelConfidence, 100)}%` }}
                  transition={{ duration: 0.8, ease: 'easeOut' }}
                />
              </div>
              {qualityCheckResult.reason && <p style={{ marginTop: '0.35rem', color: 'var(--red-600)', fontSize: '0.75rem' }}>{qualityCheckResult.reason}</p>}
              {qualityCheckResult.labels?.length > 0 && (
                <div className="labels">
                  {qualityCheckResult.labels.map((l) => <span key={l} className="label-tag">{l}</span>)}
                </div>
              )}
            </div>
          ) : qualityStatus === 'active' ? (
            <div className="pipeline-detail"><div className="skeleton skeleton-text" /><div className="skeleton skeleton-text-sm" style={{ marginTop: 5 }} /></div>
          ) : null}
        </PipelineStep>

        <PipelineStep status={duplicationStatus} index={1} title="Duplication Check" subtitle="Vector Search">
          {duplicationCheckResult ? (
            <div className="pipeline-detail">
              <p>
                Max Similarity:{' '}
                <span className={`metric-value ${duplicationCheckResult.maxSimilarity < 0.95 ? 'pass' : 'fail'}`}>
                  {(duplicationCheckResult.maxSimilarity * 100).toFixed(1)}%
                </span>
                <span className="metric-unit"> / 95% threshold</span>
              </p>
              <div className="confidence-bar">
                <motion.div
                  className={`confidence-fill ${duplicationCheckResult.maxSimilarity < 0.95 ? 'pass' : 'fail'}`}
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(duplicationCheckResult.maxSimilarity * 100, 100)}%` }}
                  transition={{ duration: 0.8, ease: 'easeOut' }}
                />
              </div>
              {duplicationCheckResult.matchedImageId && (
                <p style={{ marginTop: '0.35rem', fontSize: '0.75rem' }}>
                  Matched: <code style={{ fontSize: '0.7rem' }}>{duplicationCheckResult.matchedImageId.slice(0, 12)}...</code>
                </p>
              )}
            </div>
          ) : duplicationStatus === 'active' ? (
            <div className="pipeline-detail"><div className="skeleton skeleton-text" /><div className="skeleton skeleton-text-sm" style={{ marginTop: 5 }} /></div>
          ) : null}
        </PipelineStep>

        <PipelineStep status={indexStatus} index={2} title="Vector Indexing" subtitle="Titan Embeddings">
          {indexStatus === 'pass' ? (
            <div className="pipeline-detail"><p>Image embedded and indexed for future duplication checks</p></div>
          ) : null}
        </PipelineStep>

        <PipelineStep status={finalStatus} index={3} title={submission.status === 'ACCEPTED' ? 'Accepted' : submission.status === 'REJECTED' ? 'Rejected' : 'Final Decision'} subtitle="Store Result">
          {(submission.status === 'ACCEPTED' || submission.status === 'REJECTED') ? (
            <div className="pipeline-detail">
              <p>{submission.status === 'ACCEPTED' ? 'All verification checks passed successfully' : 'Submission rejected — see details above'}</p>
            </div>
          ) : null}
        </PipelineStep>
      </div>
    </div>
  );
}
