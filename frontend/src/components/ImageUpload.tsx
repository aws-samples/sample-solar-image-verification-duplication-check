import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from 'framer-motion';
import { requestUpload, uploadFileToS3, confirmUpload } from '../api/client';

interface ImageUploadProps {
  userId: string;
  onUploadComplete: (submissionId: string) => void;
}

const ACCEPTED_FORMATS = {
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'image/webp': ['.webp'],
  'image/bmp': ['.bmp'],
  'image/tiff': ['.tiff', '.tif'],
  'image/gif': ['.gif'],
};

export default function ImageUpload({ userId, onUploadComplete }: ImageUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<{ type: 'success' | 'error' | 'loading'; message: string } | null>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const selected = acceptedFiles[0];
    if (!selected) return;
    setFile(selected);
    setPreview(URL.createObjectURL(selected));
    setUploadStatus(null);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_FORMATS,
    maxFiles: 1,
    maxSize: 15 * 1024 * 1024,
  });

  const handleSubmit = async () => {
    if (!file || !userId.trim()) return;
    setUploading(true);
    setUploadStatus({ type: 'loading', message: 'Requesting upload URL...' });

    try {
      const { submissionId, uploadUrl } = await requestUpload(userId, file.name, file.type);
      setUploadStatus({ type: 'loading', message: 'Uploading image to S3...' });
      await uploadFileToS3(uploadUrl, file);
      setUploadStatus({ type: 'loading', message: 'Starting verification pipeline...' });
      await confirmUpload(submissionId);
      setUploadStatus({ type: 'success', message: `Submitted! ID: ${submissionId.slice(0, 8)}...` });
      setFile(null);
      setPreview(null);
      onUploadComplete(submissionId);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      setUploadStatus({ type: 'error', message });
    } finally {
      setUploading(false);
    }
  };

  return (
    <motion.div className="card" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
      <div className="card-header">
        <span className="material-symbols-rounded">cloud_upload</span>
        Upload Solar Panel Image
      </div>
      <div className="card-body">
        <motion.div
          className={`dropzone ${isDragActive ? 'active' : ''}`}
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
          animate={isDragActive ? { borderColor: '#4ade80', backgroundColor: '#f0fdf4' } : {}}
        >
          <div {...getRootProps()} style={{ cursor: 'pointer' }}>
          <input {...getInputProps()} />
          <motion.div
            style={{ marginBottom: '0.6rem' }}
            animate={isDragActive ? { y: -5 } : { y: 0 }}
            transition={{ type: 'spring', stiffness: 300 }}
          >
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="1.5">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </motion.div>
          <p><strong>Drop your image here</strong> or click to browse</p>
          <div className="dropzone-formats">
            {['JPG', 'PNG', 'WebP', 'BMP', 'TIFF', 'GIF'].map((f) => (
              <span key={f} className="format-tag">{f}</span>
            ))}
            <span style={{ color: '#9ca3af' }}>max 15 MB</span>
          </div>
          </div>
        </motion.div>

        <AnimatePresence>
          {preview && (
            <motion.div
              className="preview"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
            >
              <img src={preview} alt="Preview" />
              <p className="preview-name">{file?.name}</p>
            </motion.div>
          )}
        </AnimatePresence>

        <motion.button
          className="btn btn-primary"
          onClick={handleSubmit}
          disabled={!file || uploading || !userId.trim()}
          whileHover={!file || uploading ? {} : { scale: 1.01 }}
          whileTap={!file || uploading ? {} : { scale: 0.98 }}
        >
          {uploading ? (
            <>
              <motion.span
                className="material-symbols-rounded"
                style={{ fontSize: 17 }}
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              >sync</motion.span>
              Submitting...
            </>
          ) : (
            <>
              <span className="material-symbols-rounded" style={{ fontSize: 17 }}>send</span>
              Submit for Verification
            </>
          )}
        </motion.button>

        <AnimatePresence>
          {uploadStatus && (
            <motion.div
              className={`upload-status ${uploadStatus.type}`}
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
            >
              <span className="material-symbols-rounded">
                {uploadStatus.type === 'success' ? 'check_circle' : uploadStatus.type === 'error' ? 'error' : 'sync'}
              </span>
              {uploadStatus.message}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
