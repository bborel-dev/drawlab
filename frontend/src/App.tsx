import { useState, type ChangeEvent } from 'react'
import { traceImage } from './api'
import './App.css'

function App() {
  const [sourceUrl, setSourceUrl] = useState<string | null>(null)
  const [svg, setSvg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isTracing, setIsTracing] = useState(false)

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    setSourceUrl(URL.createObjectURL(file))
    setSvg(null)
    setError(null)
    setIsTracing(true)
    try {
      setSvg(await traceImage(file))
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Tracing failed')
    } finally {
      setIsTracing(false)
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
          <figcaption>{isTracing ? 'Drawing…' : 'Drawing'}</figcaption>
          {svg && <div className="drawing" dangerouslySetInnerHTML={{ __html: svg }} />}
        </figure>
      </section>
    </main>
  )
}

export default App
