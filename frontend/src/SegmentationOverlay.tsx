import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import type { MaskOutline } from './api'

type SegmentationOverlayProps = {
  masks: MaskOutline[]
  onRevealEndChange: (endsAt: number) => void
}

type Bounds = { left: number; right: number; top: number; bottom: number }

const REVEAL_STAGGER_MS = 450
const REVEAL_DURATION_MS = 900
const HOLD_AFTER_REVEAL_MS = 1200
const MASK_COLORS = ['#3b82f6', '#ec4899', '#a855f7', '#06b6d4', '#fb923c']

function SegmentationOverlay({ masks, onRevealEndChange }: SegmentationOverlayProps) {
  const [revealedCount, setRevealedCount] = useState(0)
  const scheduledCountRef = useRef(0)
  const nextRevealRef = useRef(0)
  const mountedRef = useRef(false)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  useEffect(() => {
    if (scheduledCountRef.current >= masks.length) return
    masks.slice(scheduledCountRef.current).forEach(() => {
      const now = performance.now()
      const revealAt = Math.max(now, nextRevealRef.current)
      nextRevealRef.current = revealAt + REVEAL_STAGGER_MS
      window.setTimeout(() => mountedRef.current && setRevealedCount((count) => count + 1), revealAt - now)
    })
    scheduledCountRef.current = masks.length
    onRevealEndChange(nextRevealRef.current - REVEAL_STAGGER_MS + REVEAL_DURATION_MS + HOLD_AFTER_REVEAL_MS)
  }, [masks, onRevealEndChange])

  const labelPositions = useMemo(() => masks.map(labelPosition), [masks])
  const revealed = masks.slice(0, revealedCount)
  if (revealed.length === 0) return null
  const { width, height } = revealed[0]

  return (
    <div className="segmentation" aria-hidden="true">
      <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        {revealed.map((mask, index) => (
          <path
            key={mask.name}
            className="mask-shape"
            d={mask.path}
            pathLength={1}
            fillRule="evenodd"
            strokeWidth={width / 320}
            style={maskStyle(index)}
          />
        ))}
      </svg>
      {revealed.map((mask, index) => (
        <span key={mask.name} className="mask-label" style={{ ...maskStyle(index), ...labelPositions[index] }}>
          {mask.name}
        </span>
      ))}
    </div>
  )
}

function maskStyle(index: number): CSSProperties {
  return { '--mask-color': MASK_COLORS[index % MASK_COLORS.length] } as CSSProperties
}

function labelPosition(mask: MaskOutline): CSSProperties {
  const { left, right, top, bottom } = outlineBounds(mask.path)
  const leftPercent = ((left + right) / 2 / mask.width) * 100
  const topPercent = ((top + bottom) / 2 / mask.height) * 100
  return {
    left: `clamp(56px, ${leftPercent}%, calc(100% - 56px))`,
    top: `clamp(16px, ${topPercent}%, calc(100% - 16px))`,
  }
}

function outlineBounds(path: string): Bounds {
  const numbers = path.match(/-?\d+(\.\d+)?/g)?.map(Number) ?? []
  const bounds = { left: Infinity, right: -Infinity, top: Infinity, bottom: -Infinity }
  for (let index = 0; index + 1 < numbers.length; index += 2) {
    bounds.left = Math.min(bounds.left, numbers[index])
    bounds.right = Math.max(bounds.right, numbers[index])
    bounds.top = Math.min(bounds.top, numbers[index + 1])
    bounds.bottom = Math.max(bounds.bottom, numbers[index + 1])
  }
  return bounds
}

export default SegmentationOverlay
