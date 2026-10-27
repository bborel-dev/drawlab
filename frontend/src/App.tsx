import { useState, type ChangeEvent } from 'react'
import { streamDrawing, type AgentEvent, type Canvas } from './api'
import DrawingCanvas from './DrawingCanvas'
import './App.css'

function App() {
  const [sourceUrl, setSourceUrl] = useState<string | null>(null)
  const [canvas, setCanvas] = useState<Canvas | null>(null)
  const [layers, setLayers] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [isDrawing, setIsDrawing] = useState(false)
  const [replayCount, setReplayCount] = useState(0)

  function handleEvent(event: AgentEvent) {
    if (event.canvas) setCanvas(event.canvas)
    const layer = event.layer
    if (layer) setLayers((current) => [...current, layer])
    if (event.status === 'error') setError(event.message)
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setSourceUrl(URL.createObjectURL(file))
    setCanvas(null)
    setLayers([])
    setError(null)
    setIsDrawing(true)
    try {
      await streamDrawing(file, handleEvent)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Drawing failed')
    } finally {
      setIsDrawing(false)
    }
  }

  return (
    <main className="studio">
      <header className="studio-header">
        <h1>Drawlab</h1>
        <input type="file" accept="image/*" onChange={handleFileChange} />
      </header>
      {error && <p className="error">{error}</p>}
      <section className="comparison">
        <figure className="panel">
          <figcaption>Original</figcaption>
          {sourceUrl && <img src={sourceUrl} alt="Original upload" />}
        </figure>
        <figure className="panel">
          <figcaption>
            {isDrawing ? 'Drawing…' : 'Drawing'}
            {!isDrawing && layers.length > 0 && (
              <button type="button" onClick={() => setReplayCount((count) => count + 1)}>
                Replay
              </button>
            )}
          </figcaption>
          {canvas && <DrawingCanvas key={replayCount} canvas={canvas} layers={layers} />}
        </figure>
      </section>
    </main>
  )
}

export default App
