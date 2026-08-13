import { useEffect, useRef } from 'react'

interface Particle {
  x: number; y: number; vx: number; vy: number
  size: number; alpha: number; hue: number
}

export default function FlowField() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const mouse = useRef({ x: -200, y: -200 })
  const particles = useRef<Particle[]>([])
  const raf = useRef(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let W = 0; let H = 0
    const COUNT = 1000
    const MOUSE_R = 160
    const MOUSE_F = 2.5

    function resize() {
      W = window.innerWidth; H = window.innerHeight
      canvas!.width = W; canvas!.height = H
      seed()
    }

    function seed() {
      const arr: Particle[] = []
      for (let i = 0; i < COUNT; i++) {
        arr.push({
          x: Math.random() * W, y: Math.random() * H,
          vx: 0, vy: 0,
          size: Math.random() * 1.6 + 0.4,
          alpha: Math.random() * 0.35 + 0.12,
          hue: 25 + Math.random() * 30, // 25-55: amber→gold
        })
      }
      particles.current = arr
    }

    // Trigonometric noise — cheap, looks organic
    function flowAngle(x: number, y: number, t: number): number {
      const s = 0.0025
      const nx = x * s; const ny = y * s
      const a = Math.sin(nx * 1.4 + t * 0.25) * Math.cos(ny * 1.6 + t * 0.2)
      const b = Math.sin(nx * 2.8 - t * 0.15) * Math.cos(ny * 2.2 + t * 0.22)
      const c = Math.cos(nx * 5.5 + t * 0.1) * Math.sin(ny * 3.8 - t * 0.16)
      return (a * 0.55 + b * 0.3 + c * 0.15) * Math.PI * 2
    }

    function tick(ts: number) {
      if (!ctx) return
      const t = ts * 0.001
      const pts = particles.current
      const mx = mouse.current.x; const my = mouse.current.y

      ctx.clearRect(0, 0, W, H)

      for (const p of pts) {
        const angle = flowAngle(p.x, p.y, t)
        const spd = 0.35 + Math.random() * 0.18
        p.vx += Math.cos(angle) * spd * 0.04
        p.vy += Math.sin(angle) * spd * 0.04

        // Mouse repulsion
        const dx = p.x - mx; const dy = p.y - my
        const dist = Math.sqrt(dx * dx + dy * dy)
        if (dist < MOUSE_R && mx > 0) {
          const f = (1 - dist / MOUSE_R) * MOUSE_F
          p.vx += (dx / (dist + 0.1)) * f * 0.08
          p.vy += (dy / (dist + 0.1)) * f * 0.08
        }

        p.vx *= 0.955; p.vy *= 0.955
        const mag = Math.sqrt(p.vx * p.vx + p.vy * p.vy)
        if (mag > 1.8) { p.vx = (p.vx / mag) * 1.8; p.vy = (p.vy / mag) * 1.8 }

        p.x += p.vx; p.y += p.vy
        if (p.x < -30) p.x = W + 30
        if (p.x > W + 30) p.x = -30
        if (p.y < -30) p.y = H + 30
        if (p.y > H + 30) p.y = -30

        // Edge fade
        const ef = Math.min(p.x / 120, (W - p.x) / 120, p.y / 120, (H - p.y) / 120, 1)
        const a = p.alpha * Math.max(0, Math.min(ef, 0.7))

        ctx.beginPath()
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2)
        ctx.fillStyle = `hsla(${p.hue}, 55%, 52%, ${a})`
        ctx.fill()
      }
      raf.current = requestAnimationFrame(tick)
    }

    function onMove(e: MouseEvent) {
      mouse.current = { x: e.clientX, y: e.clientY }
    }

    resize()
    window.addEventListener('resize', resize)
    window.addEventListener('mousemove', onMove, { passive: true })
    raf.current = requestAnimationFrame(tick)

    return () => {
      window.removeEventListener('resize', resize)
      window.removeEventListener('mousemove', onMove)
      cancelAnimationFrame(raf.current)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed', inset: 0, zIndex: 1,
        pointerEvents: 'none', opacity: 0.65,
      }}
      aria-hidden="true"
    />
  )
}
