import { useState, type ReactNode } from 'react'
import type { CompareView } from './ViewSwitch'

type CompareFrameProps = {
  sourceUrl: string
  sourceFormat: string
  view: CompareView | null
  children: ReactNode
}

const INITIAL_SPLIT = 50

function CompareFrame({ sourceUrl, sourceFormat, view, children }: CompareFrameProps) {
  const [split, setSplit] = useState(INITIAL_SPLIT)
  const beforeClip = view === 'compare' ? `inset(0 ${100 - split}% 0 0)` : 'none'
  const showsBefore = view === 'before' || view === 'compare'

  return (
    <figure className="frame">
      {children}
      {showsBefore && (
        <img className="frame-before" src={sourceUrl} alt="Original image" style={{ clipPath: beforeClip }} />
      )}
      {view === 'compare' && (
        <>
          <input
            className="compare-range"
            type="range"
            min={0}
            max={100}
            value={split}
            onChange={(event) => setSplit(Number(event.target.value))}
            aria-label="Compare before and after"
          />
          <span className="compare-line" style={{ left: `${split}%` }} aria-hidden="true" />
          <span className="compare-knob" style={{ left: `${split}%` }} aria-hidden="true">
            <svg width="22" height="12" viewBox="0 0 22 12">
              <path
                d="M6 1 L1 6 L6 11 M16 1 L21 6 L16 11"
                fill="none"
                stroke="#1C1E21"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
        </>
      )}
      {showsBefore && <span className="frame-tag frame-tag-left">Before · {sourceFormat}</span>}
      {(view === 'compare' || view === 'after') && <span className="frame-tag frame-tag-right">After · SVG</span>}
    </figure>
  )
}

export default CompareFrame
