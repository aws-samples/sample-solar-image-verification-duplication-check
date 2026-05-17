import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import { requestChequeUpload, uploadFileToS3, confirmChequeUpload } from '../api/client';

interface ChequeUploadProps {
  submissionId: string;
  onUploadComplete: () => void;
}

const ACCEPTED_FORMATS = {
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'image/webp': ['.webp'],
};

export default function ChequeUpload({ submissionId, onUploadComplete }: ChequeUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [holderName, setHolderName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState<{ type: 'success' | 'error' | 'loading'; message: string } | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const selected = acceptedFiles[0];
    if (!selected) return;
    setFile(selected);
    setPreview(URL.createObjectURL(selected));
    setStatus(null);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_FORMATS,
    maxFiles: 1,
    maxSize: 10 * 1024 * 1024,
  });

  const handleSubmit = async () => {
    if (!file || !holderName.trim()) return;
    setUploading(true);
    setStatus({ type: 'loading', message: 'Requesting upload URL...' });
    try {
      const { uploadUrl } = await requestChequeUpload(submissionId, file.name, file.type, holderName.trim());
      setStatus({ type: 'loading', message: 'Uploading cheque to S3...' });
      await uploadFileToS3(uploadUrl, file);
      setStatus({ type: 'loading', message: 'Starting cheque validation...' });
      await confirmChequeUpload(submissionId);
      setStatus({ type: 'success', message: 'Cheque submitted — validation in progress' });
      setFile(null);
      setPreview(null);
      onUploadComplete();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Cheque upload failed';
      setStatus({ type: 'error', message });
    } finally {
      setUploading(false);
    }
  };

  return (
    <motion.div
      className="cheque-upload"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      style={{ marginTop: '1rem', padding: '0.85rem', border: '1px solid var(--border, #e5e7eb)', borderRadius: 8 }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.6rem', fontWeight: 600 }}>
        <span className="material-symbols-rounded" style={{ fontSize: 18 }}>account_balance</span>
        Upload Cancelled Cheque for Fund Release
      </div>

      <div style={{ marginBottom: '0.6rem' }}>
        <label style={{ display: 'block', fontSize: '0.8rem', marginBottom: '0.25rem' }}>
          Account Holder Name (as it appears on the cheque)
        </label>
        <input
          type="text"
          value={holderName}
          onChange={(e) => setHolderName(e.target.value)}
          placeholder="e.g. Ramesh Kumar"
          style={{ width: '100%', padding: '0.45rem 0.6rem', fontSize: '0.85rem', borderRadius: 6, border: '1px solid #d1d5db' }}
        />
      </div>

      <div
        className={`dropzone ${isDragActive ? 'active' : ''}`}
        style={{ padding: '0.85rem', borderRadius: 6, border: '2px dashed #d1d5db', cursor: 'pointer', textAlign: 'center' }}
        {...getRootProps()}
      >
        <input {...getInputProps()} />
        <span className="material-symbols-rounded" style={{ fontSize: 28, color: '#22c55e' }}>upload_file</span>
        <p style={{ marginTop: '0.35rem', fontSize: '0.85rem' }}>
          <strong>Drop cancelled cheque image</strong> or click to browse (JPG/PNG/WebP, max 10 MB)
        </p>
      </div>

      <AnimatePresence>
        {preview && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            style={{ marginTop: '0.6rem' }}
          >
            <img src={preview} alt="Cheque preview" style={{ maxWidth: '100%', borderRadius: 6 }} />
            <p style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '0.2rem' }}>{file?.name}</p>
          </motion.div>
        )}
      </AnimatePresence>

      <button
        className="btn btn-primary"
        onClick={handleSubmit}
        disabled={!file || !holderName.trim() || uploading}
        style={{ marginTop: '0.6rem', width: '100%' }}
      >
        {uploading ? 'Submitting...' : 'Submit Cheque for Validation'}
      </button>

      <AnimatePresence>
        {status && (
          <motion.div
            className={`upload-status ${status.type}`}
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}
          >
            {status.message}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
