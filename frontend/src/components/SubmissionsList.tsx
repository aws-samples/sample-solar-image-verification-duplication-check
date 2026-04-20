import { motion, AnimatePresence } from 'framer-motion';
import type { Submission } from '../types';
import StatusBadge from './StatusBadge';

interface SubmissionsListProps {
  submissions: Submission[];
  activeId: string | null;
  onSelect: (submission: Submission) => void;
}

export default function SubmissionsList({ submissions, activeId, onSelect }: SubmissionsListProps) {
  if (submissions.length === 0) {
    return (
      <motion.div className="empty-state" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <div style={{ marginBottom: '0.6rem', opacity: 0.4 }}>
          <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <polyline points="21 15 16 10 5 21" />
          </svg>
        </div>
        <p>No submissions yet</p>
        <p>Upload a solar panel image to get started</p>
      </motion.div>
    );
  }

  return (
    <div className="submissions-list">
      <AnimatePresence mode="popLayout">
        {submissions.map((sub) => (
          <motion.div
            key={sub.submissionId}
            className={`submission-item ${activeId === sub.submissionId ? 'active' : ''}`}
            onClick={() => onSelect(sub)}
            layout
            initial={{ opacity: 0, x: -15 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 15 }}
            transition={{ type: 'spring', stiffness: 300, damping: 25 }}
            whileHover={{ x: 3 }}
          >
            <div>
              <div className="submission-id">{sub.submissionId.slice(0, 8)}...</div>
              <div className="submission-time">{new Date(sub.uploadedAt).toLocaleString()}</div>
            </div>
            <StatusBadge status={sub.status} />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
