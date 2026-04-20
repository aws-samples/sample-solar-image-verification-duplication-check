import { motion } from 'framer-motion';

export default function SolarScene() {
  const rays = Array.from({ length: 8 }, (_, i) => ({
    angle: i * 45,
    delay: i * 0.15,
  }));

  const panels = [
    { left: 60, width: 65 },
    { left: 140, width: 55 },
    { left: 210, width: 65 },
  ];

  const particles = Array.from({ length: 6 }, (_, i) => ({
    left: 80 + i * 35,
    delay: i * 0.4,
    duration: 2 + Math.random(),
  }));

  return (
    <div className="solar-scene">
      <motion.div
        className="solar-sun"
        animate={{ scale: [1, 1.05, 1] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
      />

      {rays.map((ray, i) => (
        <motion.div
          key={i}
          className="solar-ray"
          style={{
            top: 28,
            right: 53,
            transform: `rotate(${ray.angle}deg)`,
            transformOrigin: 'center 12px',
          }}
          animate={{ opacity: [0.3, 0.7, 0.3], height: [14, 20, 14] }}
          transition={{ duration: 2, delay: ray.delay, repeat: Infinity }}
        />
      ))}

      <div className="solar-ground" />

      {panels.map((panel, i) => (
        <motion.div
          key={i}
          className="solar-panel-anim"
          style={{ left: panel.left, width: panel.width }}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 + i * 0.15, duration: 0.5 }}
        >
          <div className="grid-line" style={{ position: 'absolute', left: '33%', top: 0, bottom: 0, width: 1 }} />
          <div className="grid-line" style={{ position: 'absolute', left: '66%', top: 0, bottom: 0, width: 1 }} />
          <div className="grid-line" style={{ position: 'absolute', top: '50%', left: 0, right: 0, height: 1 }} />
        </motion.div>
      ))}

      {particles.map((p, i) => (
        <motion.div
          key={i}
          className="energy-particle"
          style={{ left: p.left, bottom: 55 }}
          animate={{
            y: [0, -50, -70],
            opacity: [0, 1, 0],
            scale: [0, 1, 0.3],
          }}
          transition={{
            duration: p.duration,
            delay: p.delay,
            repeat: Infinity,
            ease: 'easeOut',
          }}
        />
      ))}

      <motion.div
        style={{
          position: 'absolute',
          top: 12,
          left: 20,
          color: 'rgba(255,255,255,0.9)',
          fontSize: '0.72rem',
          fontWeight: 600,
          textShadow: '0 1px 3px rgba(0,0,0,0.15)',
        }}
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.5 }}
      >
        Solar Verification System
      </motion.div>
    </div>
  );
}
