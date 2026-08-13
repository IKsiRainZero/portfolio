import { useEffect, useRef } from 'react'

export default function Spotlight() {
  const divRef = useRef<HTMLDivElement>(null)
  const mouse = useRef({ x: -500, y: -500 })
  const smooth = useRef({ x: -500, y: -500 })
  const raf = useRef(0)

  useEffect(() => {
    function onMove(e: MouseEvent) {
      mouse.current = { x: e.clientX, y: e.clientY }
    }

    function tick() {
      const m = mouse.current; const s = smooth.current
      s.x += (m.x - s.x) * 0.06
      s.y += (m.y - s.y) * 0.06

      if (divRef.current && m.x > 0) {
        divRef.current.style.background = `
          radial-gradient(
            circle 350px at ${s.x}px ${s.y}px,
            rgba(212,140,64,0.07) 0%,
            rgba(212,140,64,0.03) 35%,
            transparent 65%
          )
        `
      }
      raf.current = requestAnimationFrame(tick)
    }

    window.addEventListener('mousemove', onMove, { passive: true })
    raf.current = requestAnimationFrame(tick)

    return () => {
      window.removeEventListener('mousemove', onMove)
      cancelAnimationFrame(raf.current)
    }
  }, [])

  return (
    <div
      ref={divRef}
      style={{
        position: 'fixed', inset: 0, zIndex: 4,
        pointerEvents: 'none',
        background: 'radial-gradient(circle 350px at -500px -500px, transparent 0%, transparent 100%)',
      }}
      aria-hidden="true"
    />
  )
}
