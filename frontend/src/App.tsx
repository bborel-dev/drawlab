import { useState } from 'react'
import Backdrop from './Backdrop'
import ConverterPage from './ConverterPage'
import EditorPage from './EditorPage'
import HackathonBadge from './HackathonBadge'
import type { Drawing } from './layers'
import SiteHeader, { type Page } from './SiteHeader'
import './App.css'

type EditorSession = {
  drawing: Drawing
  version: number
}

function App() {
  const [page, setPage] = useState<Page>('convert')
  const [session, setSession] = useState<EditorSession | null>(null)

  function openEditor(drawing: Drawing) {
    setSession((current) =>
      current?.drawing.layers === drawing.layers ? current : { drawing, version: (current?.version ?? 0) + 1 },
    )
    setPage('editor')
  }

  return (
    <>
      <Backdrop />
      <SiteHeader page={page} editorReady={session !== null} onNavigate={setPage} />
      <HackathonBadge />
      <div hidden={page !== 'convert'}>
        <ConverterPage onEdit={openEditor} />
      </div>
      {session && (
        <div hidden={page !== 'editor'}>
          <EditorPage key={session.version} drawing={session.drawing} />
        </div>
      )}
    </>
  )
}

export default App
