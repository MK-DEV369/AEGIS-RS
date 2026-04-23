import { motion } from 'framer-motion'

const orbs = [
	{ className: 'orb orb-a', delay: 0, duration: 11 },
	{ className: 'orb orb-b', delay: 1.4, duration: 13 },
	{ className: 'orb orb-c', delay: 2.1, duration: 15 },
]

export function AnimatedOrbs() {
	return (
		<div className="ambient-orbs" aria-hidden="true">
			{orbs.map((orb) => (
				<motion.span
					key={orb.className}
					className={orb.className}
					initial={{ opacity: 0, scale: 0.92 }}
					animate={{ opacity: 1, scale: [0.98, 1.04, 0.98], y: [0, -18, 0] }}
					transition={{ duration: orb.duration, delay: orb.delay, repeat: Infinity, ease: 'easeInOut' }}
				/>
			))}
		</div>
	)
}