import { useLayoutEffect, useRef, type RefObject } from 'react'
import logo from './assets/logo.svg?raw'
import Backdrop from './Backdrop'

const CLIP_ID = 'brand-hole-clip'
const MARK_HEIGHT = 24
const NAME_GAP = 7
const NAME_BASELINE = 18
const LOGO_VIEW_BOX = logo.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/)?.slice(1).map(Number) ?? [1, 1]
const LOGO_SCALE = MARK_HEIGHT / LOGO_VIEW_BOX[1]
const LOGO_WIDTH = LOGO_VIEW_BOX[0] * LOGO_SCALE
const LOGO_OFFSET = logo.match(/<g transform="translate\(([-\d.]+),([-\d.]+)\)">/)?.slice(1).map(Number) ?? [0, 0]
const LOGO_PATHS = [...logo.matchAll(/ d="([^"]+)"/g)].map((match) => match[1])
const LOGO_TRANSFORM = `scale(${LOGO_SCALE}) translate(${LOGO_OFFSET[0]},${LOGO_OFFSET[1]})`

function BrandMark() {
  const holeRef = useRef<HTMLSpanElement>(null)
  const viewRef = useRef<HTMLSpanElement>(null)
  useViewportAlignment(holeRef, viewRef)

  return (
    <span className="brand">
      <span className="brand-logo" style={{ width: LOGO_WIDTH }} aria-hidden="true" />
      <span className="brand-name">Drawlab</span>
      <svg className="brand-clip" width="0" height="0" aria-hidden="true">
        <clipPath id={CLIP_ID} clipPathUnits="userSpaceOnUse">
          {LOGO_PATHS.map((data) => (
            <path key={data} d={data} transform={LOGO_TRANSFORM} />
          ))}
          <text
            x={LOGO_WIDTH + NAME_GAP}
            y={NAME_BASELINE}
            fontFamily="Inter, system-ui, sans-serif"
            fontSize="17"
            fontWeight="700"
            letterSpacing="-0.17"
          >
            Drawlab
          </text>
        </clipPath>
      </svg>
      <span ref={holeRef} className="brand-hole" style={{ clipPath: `url(#${CLIP_ID})` }} aria-hidden="true">
        <span ref={viewRef} className="brand-hole-view">
          <Backdrop />
        </span>
      </span>
    </span>
  )
}

function useViewportAlignment(
  holeRef: RefObject<HTMLSpanElement | null>,
  viewRef: RefObject<HTMLSpanElement | null>,
): void {
  useLayoutEffect(() => {
    function align() {
      const hole = holeRef.current
      const view = viewRef.current
      if (!hole || !view) return
      const { left, top } = hole.getBoundingClientRect()
      view.style.transform = `translate(${-left}px, ${-top}px)`
    }
    align()
    window.addEventListener('resize', align)
    window.addEventListener('scroll', align, { passive: true })
    return () => {
      window.removeEventListener('resize', align)
      window.removeEventListener('scroll', align)
    }
  }, [holeRef, viewRef])
}

export default BrandMark
