import { motion } from 'framer-motion';

interface StatusBadgeProps {
  status: string;
}

const STATUS_CONFIG: Record<string, { className: string; label: string; icon: string }> = {
  PENDING: { className: 'badge-pending', label: 'Pending', icon: 'schedule' },
  PROCESSING: { className: 'badge-processing', label: 'Processing', icon: 'sync' },
  ACCEPTED: { className: 'badge-accepted', label: 'Accepted', icon: 'check_circle' },
  REJECTED: { className: 'badge-rejected', label: 'Rejected', icon: 'cancel' },
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.PENDING;
  return (
    <motion.span
      className={`badge ${config.className}`}
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      key={status}
      transition={{ type: 'spring', stiffness: 400, damping: 15 }}
    >
      <span className="material-symbols-rounded" style={{ fontSize: 12 }}>{config.icon}</span>
      {config.label}
    </motion.span>
  );
}
