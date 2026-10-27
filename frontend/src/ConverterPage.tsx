import { useCallback, useEffect, useRef, useState } from 'react'
import { applyAgentEvent, initialAgentStates } from './agents'
import { streamDrawing, type Canvas } from './api'
import CompareFrame from './CompareFrame'
import DrawingCanvas from './DrawingCanvas'
import { drawingProgress } from './drawingProgress'
import DrawingStatus from './DrawingStatus'
import DropZone from './DropZone'
import Examples from './Examples'
import { downloadSvg, svgDocument, svgFileName } from './layers'
import ViewSwitch, { type CompareView } from './ViewSwitch'

type Phase = 'empty' | 'drawing' | 'done'

type Source = {
  url: string
  name: string
  format: string
}

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024

function ConverterPage() {
  const [phase, setPhase] = useState<Phase>('empty')
  const [source, setSource] = useState<Source | null>(null)
  const [canvas, setCanvas] = useState<Canvas | null>(null)
  const [layers, setLayers] = useState<string[]>([])
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

  const handleLayerStart = useCallback((name: string) => {
    setCurrentLayer(name)
    setStartedLayers((count) => count + 1)
  }, [])

  const handleDrawingEnd = useCallback((endsAt: number) => setDrawingEndsAt(endsAt), [])

  function resetDrawing() {
    abortRef.current?.abort()
    setCanvas(null)
    setLayers([])
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
    setPhase('drawing')
  }

  if (phase === 'empty' || !source) {
    return (
      <main className="converter converter-empty">
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
        <Examples onFile={startDrawing} />
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
  })

  return (
    <main className="converter">
      <div className="converter-row">
        <div className="file-info">
          <span className="file-name">{source.name}</span>
          {phase === 'drawing' ? (
            <span className="badge badge-blue">Drawing</span>
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
        {canvas ? (
          <DrawingCanvas
            key={replayCount}
            canvas={canvas}
            layers={layers}
            onLayerStart={handleLayerStart}
            onDrawingEndChange={handleDrawingEnd}
          />
        ) : (
          <img className="frame-placeholder" src={source.url} alt="Original image being studied" />
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
            <button type="button" className="button button-primary" disabled title="Coming next">
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
