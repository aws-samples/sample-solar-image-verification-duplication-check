import { motion } from 'framer-motion';
import type { Submission } from '../types';

interface DashboardStatsProps {
  submissions: Submission[];
}

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35 } },
};

export default function DashboardStats({ submissions }: DashboardStatsProps) {
  const total = submissions.length;
  const pending = submissions.filter((s) => s.status === 'PENDING' || s.status === 'PROCESSING').length;
  const accepted = submissions.filter((s) => s.status === 'ACCEPTED').length;
  const rejected = submissions.filter((s) => s.status === 'REJECTED').length;

  const stats = [
    { key: 'total', value: total, label: 'Total', icon: 'folder_open' },
    { key: 'pending', value: pending, label: 'In Progress', icon: 'hourglass_top' },
    { key: 'accepted', value: accepted, label: 'Accepted', icon: 'check_circle' },
    { key: 'rejected', value: rejected, label: 'Rejected', icon: 'cancel' },
  ];

  return (
    <motion.div className="stats-bar" variants={container} initial="hidden" animate="show">
      {stats.map((s) => (
        <motion.div key={s.key} className={`stat-card ${s.key}`} variants={item} whileHover={{ y: -2, boxShadow: '0 6px 12px rgba(0,0,0,0.08)' }}>
          <div className={`stat-icon ${s.key}`}>
            <span className="material-symbols-rounded">{s.icon}</span>
          </div>
          <div>
            <motion.div
              className="stat-value"
              key={s.value}
              initial={{ scale: 1.3, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 300 }}
            >
              {s.value}
            </motion.div>
            <div className="stat-label">{s.label}</div>
          </div>
        </motion.div>
      ))}
    </motion.div>
  );
}
