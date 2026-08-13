import { motion } from 'framer-motion'
import SatelliteRing from '../SatelliteRing'
import FloatingTags from '../FloatingTags'
import StatusLights from '../StatusLights'
import GlowBar from '../GlowBar'
import styles from './WelcomePage.module.css'

interface Props {
  processing: boolean
  onStart: () => void
}

const TITLE = 'Crescent Workbench'
const SUBTITLE = '你的 AI 职业规划伙伴。描述你的技能与经历，发现匹配的职业方向，获得从"不知道"到"能做到"的完整行动支持。'

const titleContainer = {
  animate: {
    transition: { staggerChildren: 0.08, delayChildren: 0.3 },
  },
}
const titleItem = {
  initial: { y: 18, opacity: 0 },
  animate: { y: 0, opacity: 1, transition: { duration: 0.5, ease: 'easeOut' as const } },
}

export default function WelcomePage({ processing, onStart }: Props) {
  return (
    <div className={styles.welcome}>
      <FloatingTags />
      <SatelliteRing />
      <StatusLights />
      <GlowBar />
      <motion.div
        className={styles.titleRow}
        variants={titleContainer}
        initial="initial"
        animate="animate"
      >
        {TITLE.split(' ').map((word, i) => (
          <motion.span key={i} className={styles.titleWord} variants={titleItem}>
            {word}
          </motion.span>
        ))}
      </motion.div>

      <motion.p
        className={styles.subtitle}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.9, duration: 0.6 }}
      >
        {SUBTITLE}
      </motion.p>

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.3, duration: 0.5 }}
        whileHover={processing ? undefined : { scale: 1.03 }}
        whileTap={processing ? undefined : { scale: 0.97 }}
      >
        <button
          className={styles.startBtn}
          onClick={onStart}
          disabled={processing}
          type="button"
        >
          <span className={styles.startBtnInner}>
            {processing ? (
              <>
                <span className={styles.spinner} />
                启动中…
              </>
            ) : (
              '开始'
            )}
          </span>
        </button>
      </motion.div>

      <motion.p
        className={styles.hint}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.8, duration: 0.5 }}
      >
        按 <kbd>Ctrl+J</kbd> 随时打开对话
      </motion.p>
    </div>
  )
}
