import { useState } from 'react'
import Backdrop from './Backdrop'
import ConverterPage from './ConverterPage'
import EditorPage from './EditorPage'
import EditorStart from './EditorStart'
import HackathonBadge from './HackathonBadge'
import type { Drawing } from './layers'
import { useRecentDrawings } from './recentDrawings'
import SiteHeader, { type Page } from './SiteHeader'
import { importSvg } from './svgImport'
import './App.css'

type OpenDrawing = {
  id: string
  version: number
}

const MAX_SVG_BYTES = 15 * 1024 * 1024

function App() {
  const [page, setPage] = useState<Page>('convert')
  const [open, setOpen] = useState<OpenDrawing | null>(null)
  const [importError, setImportError] = useState<string | null>(null)
  const recents = useRecentDrawings()
  const openRecent = recents.items.find((item) => item.id === open?.id) ?? null
  const editing = page === 'editor' && openRecent !== null

  function openDrawing(id: string) {
    setOpen((current) => ({ id, version: (current?.version ?? 0) + 1 }))
    setImportError(null)
    setPage('editor')
  }

  function editDrawing(drawing: Drawing) {
    openDrawing(recents.add(drawing))
  }

  async function importFile(file: File) {
    try {
      if (file.size > MAX_SVG_BYTES) throw new Error('This SVG is over 15 MB.')
      const { drawing, drawnByDrawlab } = importSvg(await file.text(), file.name)
      openDrawing(recents.add({ ...drawing, foreign: !drawnByDrawlab }))
    } catch (caught) {
      setImportError(caught instanceof Error ? caught.message : 'This SVG could not be opened.')
    }
  }

  return (
    <div className={editing ? 'app app-fixed' : 'app'}>
      <Backdrop />
      {!editing && (
        <>
          <SiteHeader page={page} onNavigate={setPage} />
          <HackathonBadge />
        </>
      )}
      <div hidden={page !== 'convert'}>
        <ConverterPage onDrawn={recents.add} onEdit={editDrawing} />
      </div>
      {page === 'editor' && !openRecent && (
        <EditorStart
          recents={recents.items}
          error={importError}
          onOpenRecent={openDrawing}
          onRemoveRecent={recents.remove}
          onImport={importFile}
          onConvert={() => setPage('convert')}
        />
      )}
      {open && openRecent && (
        <div className="editor-view" hidden={!editing}>
          <EditorPage
            key={open.version}
            drawingId={openRecent.id}
            drawing={openRecent.drawing}
            active={editing}
            onSave={recents.saveLayers}
            onBack={() => setOpen(null)}
          />
        </div>
      )}
    </div>
  )
}

export default App
