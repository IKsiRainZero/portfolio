import { AnimatePresence, motion } from 'framer-motion'
import type { PageId } from '../hooks/usePageNavigation'
import WelcomePage from './pages/WelcomePage'
import DiscoverPage from './pages/DiscoverPage'
import PlanPage from './pages/PlanPage'
import ActPage from './pages/ActPage'
import styles from './PageRouter.module.css'

interface PageRouterProps {
  currentPage: PageId
  processing: boolean
  hasSession: boolean
  panelStates: Record<string, string>
  panelPayloads: Record<string, Record<string, unknown>>
  onStart: () => void
  onConfirm: (pid: string) => void
  onBackToWelcome?: () => void
}

const pageTransition = {
  initial: { y: 40, opacity: 0, filter: 'blur(8px)' },
  animate: { y: 0, opacity: 1, filter: 'blur(0)' },
  exit: { y: -24, opacity: 0, filter: 'blur(4px)' },
  transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] as const },
}

export default function PageRouter({
  currentPage, processing, hasSession, panelStates, panelPayloads, onStart, onConfirm, onBackToWelcome,
}: PageRouterProps) {
  return (
    <>
      {currentPage !== 'welcome' && onBackToWelcome && (
        <button
          type="button"
          className={styles.backBtn}
          onClick={onBackToWelcome}
        >
          &larr; 返回首页
        </button>
      )}

      <AnimatePresence mode="wait">
        <motion.div
          key={currentPage}
          className={styles.page}
          {...pageTransition}
        >
          {currentPage === 'welcome' && (
            <WelcomePage processing={processing} onStart={onStart} />
          )}
          {currentPage === 'discover' && (
            <DiscoverPage
              panelStates={panelStates}
              panelPayloads={panelPayloads}
              hasSession={hasSession}
              onConfirm={onConfirm}
            />
          )}
          {currentPage === 'plan' && (
            <PlanPage
              panelStates={panelStates}
              panelPayloads={panelPayloads}
              hasSession={hasSession}
              onConfirm={onConfirm}
            />
          )}
          {currentPage === 'act' && (
            <ActPage
              panelStates={panelStates}
              panelPayloads={panelPayloads}
              hasSession={hasSession}
              onConfirm={onConfirm}
            />
          )}
        </motion.div>
      </AnimatePresence>
    </>
  )
}
