import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { applyAgentEvent, initialAgentStates } from './agents'
import { streamDrawing, type Canvas, type MaskOutline } from './api'
import CompareFrame from './CompareFrame'
import DrawingCanvas from './DrawingCanvas'
import { drawingProgress } from './drawingProgress'
import DrawingStatus from './DrawingStatus'
import DropZone from './DropZone'
import { downloadSvg, svgDocument, svgFileName, type Drawing } from './layers'
import SegmentationOverlay from './SegmentationOverlay'
import ViewSwitch, { type CompareView } from './ViewSwitch'

type Phase = 'empty' | 'drawing' | 'done'

type Source = {
  url: string
  name: string
  format: string
}

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024

type ConverterPageProps = {
  onDrawn: (drawing: Drawing) => void
  onEdit: (drawing: Drawing) => void
}

function ConverterPage({ onDrawn, onEdit }: ConverterPageProps) {
  const [phase, setPhase] = useState<Phase>('empty')
  const [source, setSource] = useState<Source | null>(null)
  const [canvas, setCanvas] = useState<Canvas | null>(null)
  const [layers, setLayers] = useState<string[]>([])
  const [masks, setMasks] = useState<MaskOutline[]>([])
  const [maskRevealEndsAt, setMaskRevealEndsAt] = useState<number | null>(null)
  const [segmentationShown, setSegmentationShown] = useState(false)
  const [agentStates, setAgentStates] = useState(initialAgentStates)
  const [currentLayer, setCurrentLayer] = useState<string | null>(null)
  const [startedLayers, setStartedLayers] = useState(0)
  const [streamDone, setStreamDone] = useState(false)
  const [drawingEndsAt, setDrawingEndsAt] = useState<number | null>(null)
  const [replayCount, setReplayCount] = useState(0)
  const [view, setView] = useState<CompareView>('compare')
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const startedAtRef = useRef(0)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (phase !== 'drawing' || !streamDone || drawingEndsAt === null) return
    const timer = window.setTimeout(() => {
      setPhase('done')
      setCurrentLayer(null)
      setSeconds((current) => current || Math.round((performance.now() - startedAtRef.current) / 1000))
    }, Math.max(0, drawingEndsAt - performance.now()))
    return () => window.clearTimeout(timer)
  }, [phase, streamDone, drawingEndsAt])

  useEffect(() => {
    if (!canvas || segmentationShown || (masks.length > 0 && maskRevealEndsAt === null)) return
    const timer = window.setTimeout(
      () => setSegmentationShown(true),
      Math.max(0, (maskRevealEndsAt ?? 0) - performance.now()),
    )
    return () => window.clearTimeout(timer)
  }, [canvas, segmentationShown, masks.length, maskRevealEndsAt])

  const sourceName = source?.name
  const drawing = useMemo<Drawing | null>(
    () => (streamDone && canvas && sourceName ? { canvas, layers, sourceName } : null),
    [streamDone, canvas, layers, sourceName],
  )

  useEffect(() => {
    if (phase === 'done' && drawing) onDrawn(drawing)
  }, [phase, drawing, onDrawn])

  const handleLayerStart = useCallback((name: string) => {
    setCurrentLayer(name)
    setStartedLayers((count) => count + 1)
  }, [])

  const handleDrawingEnd = useCallback((endsAt: number) => setDrawingEndsAt(endsAt), [])

  const handleMaskRevealEnd = useCallback((endsAt: number) => setMaskRevealEndsAt(endsAt), [])

  function resetDrawing() {
    abortRef.current?.abort()
    setCanvas(null)
    setLayers([])
    setMasks([])
    setMaskRevealEndsAt(null)
    setSegmentationShown(false)
    setAgentStates(initialAgentStates())
    setCurrentLayer(null)
    setStartedLayers(0)
    setStreamDone(false)
    setDrawingEndsAt(null)
    setView('compare')
    setSeconds(0)
    setError(null)
  }

  function startOver(message: string | null = null) {
    resetDrawing()
    setSource(null)
    setPhase('empty')
    setError(message)
  }

  async function startDrawing(file: File) {
    if (file.size > MAX_UPLOAD_BYTES) {
      startOver('This image is over 10 MB. Try a smaller one.')
      return
    }
    resetDrawing()
    setSource({ url: URL.createObjectURL(file), name: file.name, format: fileFormat(file) })
    setPhase('drawing')
    startedAtRef.current = performance.now()
    const controller = new AbortController()
    abortRef.current = controller
    const outcome = { failure: null as string | null, layerCount: 0 }
    try {
      await streamDrawing(
        file,
        (event) => {
          setAgentStates((current) => applyAgentEvent(current, event))
          if (event.canvas) setCanvas(event.canvas)
          const mask = event.mask
          if (mask) setMasks((current) => [...current, mask])
          const layer = event.layer
          if (layer) {
            outcome.layerCount += 1
            setLayers((current) => [...current, layer])
          }
          if (event.status === 'error') outcome.failure = event.message
        },
        controller.signal,
      )
    } catch (caught) {
      if (controller.signal.aborted) return
      outcome.failure = caught instanceof Error ? caught.message : 'Drawing failed'
    }
    if (outcome.failure || outcome.layerCount === 0) {
      startOver(outcome.failure ?? 'No layers could be drawn from this image.')
      return
    }
    setStreamDone(true)
  }

  function replay() {
    setReplayCount((count) => count + 1)
    setCurrentLayer(null)
    setStartedLayers(0)
    setDrawingEndsAt(null)
    setMaskRevealEndsAt(null)
    setSegmentationShown(false)
    setPhase('drawing')
  }

  if (phase === 'empty' || !source) {
    return (
      <main className="converter converter-empty glass">
        <h1>
          Turn any image into
          <br />
          editable vectors.
        </h1>
        <p className="lede">AI agents redraw your image stroke by stroke, as clean SVG layers with real names.</p>
        {error && (
          <p className="error-banner" role="alert">
            {error}
          </p>
        )}
        <DropZone onFile={startDrawing} />
      </main>
    )
  }

  const drawingSvg = canvas ? svgDocument(canvas, layers) : ''
  const status = drawingProgress({
    states: agentStates,
    currentLayer,
    startedLayers,
    totalLayers: layers.length,
    streamDone,
    revealingMasks: canvas !== null && !segmentationShown,
  })

  return (
    <main className="converter glass">
      <div className="converter-row">
        <div className="file-info">
          <span className="file-name">{source.name}</span>
          {phase === 'drawing' ? (
            <span className="badge badge-neutral">Drawing</span>
          ) : (
            <span className="badge badge-green">Done in {seconds} s</span>
          )}
        </div>
        {phase === 'drawing' ? (
          <button type="button" className="button button-secondary" onClick={() => startOver()}>
            Cancel
          </button>
        ) : (
          <ViewSwitch view={view} onChange={setView} />
        )}
      </div>

      <CompareFrame sourceUrl={source.url} sourceFormat={source.format} view={phase === 'done' ? view : null}>
        {canvas && segmentationShown ? (
          <DrawingCanvas
            key={replayCount}
            canvas={canvas}
            layers={layers}
            onLayerStart={handleLayerStart}
            onDrawingEndChange={handleDrawingEnd}
          />
        ) : (
          <>
            <img
              className={masks.length > 0 ? 'frame-placeholder frame-placeholder-segmented' : 'frame-placeholder'}
              src={source.url}
              alt="Original image being studied"
            />
            <SegmentationOverlay key={replayCount} masks={masks} onRevealEndChange={handleMaskRevealEnd} />
          </>
        )}
      </CompareFrame>

      {phase === 'drawing' ? (
        <DrawingStatus {...status} />
      ) : (
        <div className="converter-row">
          <p className="result-stats">
            {layers.length} named layers · {Math.max(1, Math.round(drawingSvg.length / 1024))} KB · opens in Figma
          </p>
          <div className="actions">
            <button type="button" className="button button-ghost" onClick={() => startOver()}>
              New image
            </button>
            <button type="button" className="button button-ghost" onClick={replay}>
              Replay
            </button>
            <button
              type="button"
              className="button button-secondary"
              onClick={() => downloadSvg(drawingSvg, svgFileName(source.name))}
            >
              Download SVG
            </button>
            <button
              type="button"
              className="button button-primary"
              disabled={!drawing}
              onClick={() => drawing && onEdit(drawing)}
            >
              Edit layers →
            </button>
          </div>
        </div>
      )}
    </main>
  )
}

function fileFormat(file: File): string {
  const extension = file.name.split('.').pop()?.toUpperCase() ?? 'IMAGE'
  return extension === 'JPEG' ? 'JPG' : extension
}

export default ConverterPage
