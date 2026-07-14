import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Submission } from './types';
import { getUserSubmissions, getSubmissionStatus } from './api/client';
import ImageUpload from './components/ImageUpload';
import SubmissionsList from './components/SubmissionsList';
import SubmissionDetail from './components/SubmissionDetail';
import DashboardStats from './components/DashboardStats';
import ToastContainer from './components/ToastContainer';
import SolarScene from './components/SolarScene';
import type { Toast } from './components/ToastContainer';

export default function App() {
  const [userId, setUserId] = useState('demo-user');
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [activeSubmission, setActiveSubmission] = useState<Submission | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const prevStatusRef = useRef<Map<string, string>>(new Map());

  const addToast = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = crypto.randomUUID();
    setToasts((prev) => [...prev, { ...toast, id }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  }, []);

  const refreshSubmissions = useCallback(async () => {
    if (!userId.trim()) return;
    try {
      const data = await getUserSubmissions(userId);
      data.forEach((sub) => {
        const prev = prevStatusRef.current.get(sub.submissionId);
        if (prev && prev !== sub.status) {
          if (sub.status === 'ACCEPTED') {
            addToast({ type: 'success', title: 'Verification Passed', message: `Submission ${sub.submissionId.slice(0, 8)} accepted` });
          } else if (sub.status === 'REJECTED') {
            addToast({ type: 'error', title: 'Verification Failed', message: sub.rejectionReason || `Submission ${sub.submissionId.slice(0, 8)} rejected` });
          }
        }
        prevStatusRef.current.set(sub.submissionId, sub.status);
      });
      setSubmissions(data);
    } catch {
      // API not available yet
    }
  }, [userId, addToast]);

  useEffect(() => {
    refreshSubmissions();
    const interval = setInterval(refreshSubmissions, 6000);
    return () => clearInterval(interval);
  }, [refreshSubmissions]);

  useEffect(() => {
    if (!activeSubmission) return;
    if (activeSubmission.status === 'ACCEPTED' || activeSubmission.status === 'REJECTED') return;

    const interval = setInterval(async () => {
      try {
        const updated = await getSubmissionStatus(activeSubmission.submissionId);
        setActiveSubmission(updated);
        setSubmissions((prev) => prev.map((s) => (s.submissionId === updated.submissionId ? updated : s)));
        prevStatusRef.current.set(updated.submissionId, updated.status);
        if (updated.status === 'ACCEPTED' || updated.status === 'REJECTED') clearInterval(interval);
      } catch {
        // ignore
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [activeSubmission]);

  const handleUploadComplete = async (submissionId: string) => {
    addToast({ type: 'info', title: 'Upload Complete', message: 'Verification pipeline started' });
    try {
      const sub = await getSubmissionStatus(submissionId);
      prevStatusRef.current.set(sub.submissionId, sub.status);
      setSubmissions((prev) => [sub, ...prev]);
      setActiveSubmission(sub);
    } catch {
      await refreshSubmissions();
    }
  };

  return (
    <div className="app">
      <div className="accent-bar" />
      <header className="header">
        <motion.div
          className="header-icon"
          initial={{ rotate: -10 }}
          animate={{ rotate: 0 }}
          transition={{ type: 'spring', stiffness: 200 }}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
        </motion.div>
        <div>
          <h1>MNRE Solar Panel Verification</h1>
          <p>Ministry of New and Renewable Energy &mdash; Subsidy Image Verification</p>
        </div>
      </header>

      <DashboardStats submissions={submissions} />

      <main className="main">
        <div>
          <motion.div className="card" style={{ marginBottom: '0.85rem' }} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <div className="card-header">
              <span className="material-symbols-rounded">person</span>
              User Identity
            </div>
            <div className="card-body">
              <div className="user-input">
                <input type="text" placeholder="Enter your User ID" value={userId} onChange={(e) => setUserId(e.target.value)} />
                <button className="btn btn-secondary" onClick={refreshSubmissions}>
                  <span className="material-symbols-rounded" style={{ fontSize: 15 }}>refresh</span>
                </button>
              </div>
            </div>
          </motion.div>

          <ImageUpload userId={userId} onUploadComplete={handleUploadComplete} />

          <motion.div className="card" style={{ marginTop: '0.85rem' }} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
            <div className="card-header">
              <span className="material-symbols-rounded">list_alt</span>
              Submissions ({submissions.length})
              <span style={{ marginLeft: 'auto' }}>
                <span className="auto-refresh">
                  <motion.span
                    className="material-symbols-rounded"
                    style={{ fontSize: 13 }}
                    animate={{ rotate: 360 }}
                    transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                  >sync</motion.span>
                  Live
                </span>
              </span>
            </div>
            <div className="card-body" style={{ padding: submissions.length ? '0.4rem' : undefined }}>
              <div className="submissions-scroll">
                <SubmissionsList submissions={submissions} activeId={activeSubmission?.submissionId ?? null} onSelect={setActiveSubmission} />
              </div>
            </div>
          </motion.div>
        </div>

        <div className="right-column">
          <AnimatePresence mode="wait">
            {activeSubmission ? (
              <motion.div
                key={activeSubmission.submissionId}
                className={`card ${activeSubmission.status === 'ACCEPTED' ? 'accepted-glow' : ''}`}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3 }}
              >
                <SolarScene />
                <div className="card-header">
                  <span className="material-symbols-rounded">verified</span>
                  Verification Pipeline
                </div>
                <div className="card-body">
                  <SubmissionDetail submission={activeSubmission} />
                </div>
              </motion.div>
            ) : (
              <motion.div className="card" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <SolarScene />
                <div className="card-body">
                  <div className="empty-state">
                    <p>Select a submission to view details</p>
                    <p>Upload a solar panel image to begin verification</p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </main>

      <ToastContainer toasts={toasts} />
    </div>
  );
}
