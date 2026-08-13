import { useEffect, useRef } from 'react'
import styles from './FloatingTags.module.css'

const TAGS = [
  'Python', 'FastAPI', 'DeepSeek', 'React', 'TypeScript', 'Vite',
  'ChromaDB', 'LangGraph', 'framer-motion', 'SSE',
  'PyInstaller', 'Jinja2', 'CSS Modules', 'sentence-transformers',
  'PyPDF', 'jieba', 'RAG',
]

export default function FloatingTags() {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    function onMove(e: MouseEvent) {
      const cx = e.clientX / window.innerWidth - 0.5
      const cy = e.clientY / window.innerHeight - 0.5
      el!.style.setProperty('--mx', String(cx))
      el!.style.setProperty('--my', String(cy))
    }

    window.addEventListener('mousemove', onMove, { passive: true })
    return () => window.removeEventListener('mousemove', onMove)
  }, [])

  return (
    <div ref={containerRef} className={styles.field} aria-hidden="true">
      {TAGS.map((tag, i) => {
        const row = Math.floor(i / 6)
        const col = i % 6
        const x = 5 + col * 17 + (row % 2 === 0 ? 0 : 8)
        const y = 5 + row * 25 + Math.random() * 10
        return (
          <span
            key={tag}
            className={styles.tag}
            style={{
              left: `${x}%`,
              top: `${y}%`,
              animationDelay: `${i * 0.7 + Math.random() * 2}s`,
              animationDuration: `${18 + Math.random() * 14}s`,
              opacity: 0.10 + Math.random() * 0.12,
              fontSize: `${11 + Math.random() * 4}px`,
            }}
          >
            {tag}
          </span>
        )
      })}
    </div>
  )
}
