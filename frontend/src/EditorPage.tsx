import { useEffect, useRef, useState } from 'react'
import EditorCanvas from './EditorCanvas'
import {
  editedSvgDocument,
  moveLayerTo,
  parseLayers,
  savedLayerMarkups,
  toggleLayer,
  togglePart,
  updateLayer,
  type EditorLayer,
  type LayerPatch,
} from './editorLayers'
import { BackIcon, RedoIcon, SparkleIcon, UndoIcon } from './icons'
import { downloadSvg, svgFileName, type Drawing } from './layers'
import LayersPanel from './LayersPanel'
import PropertiesPanel from './PropertiesPanel'
import { useHistory, useUndoShortcuts } from './useHistory'
import ZoomControl from './ZoomControl'
import { FIT_VIEW, zoomAround, type View } from './zoom'

type SaveLayers = (drawingId: string, layers: string[]) => void

type EditorPageProps = {
  drawingId: string
  drawing: Drawing
  active: boolean
  onSave: SaveLayers
  onBack: () => void
}

const AUTOSAVE_DELAY_MS = 800

function EditorPage({ drawingId, drawing, active, onSave, onBack }: EditorPageProps) {
  const history = useHistory(() => parseLayers(drawing.layers))
  const { present: layers, update, undo, redo } = history
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [view, setView] = useState<View>(FIT_VIEW)
  const selected = layers.find((layer) => layer.id === selectedId) ?? null
  useUndoShortcuts(active, undo, redo)
  useAutosave(layers, drawingId, onSave)

  function changeLayer(id: string, patch: LayerPatch, gesture?: string) {
    update((current) => updateLayer(current, id, patch), gesture && `${gesture}:${id}`)
  }

  function reorderLayer(id: string, index: number) {
    update((current) => moveLayerTo(current, id, index))
  }

  function exportSvg() {
    downloadSvg(editedSvgDocument(drawing.canvas, layers), svgFileName(drawing.sourceName))
  }

  return (
    <main className="editor glass">
      <div className="converter-row">
        <div className="file-info">
          <button
            type="button"
            className="back-button"
            onClick={onBack}
            aria-label="Back to your drawings"
            title="Back to your drawings"
          >
            <BackIcon />
          </button>
          <span className="file-name">{drawing.sourceName}</span>
          <span className="badge badge-neutral">{layers.length} layers</span>
          {drawing.foreign && (
            <span className="badge badge-neutral" title="Layer names come from the file, not from Drawlab">
              Imported SVG
            </span>
          )}
        </div>
        <div className="editor-tools">
          <div className="view-switch" role="group" aria-label="History">
            <button
              type="button"
              className="icon-switch"
              disabled={!history.canUndo}
              onClick={undo}
              aria-label="Undo"
              title="Undo (Ctrl+Z)"
            >
              <UndoIcon />
            </button>
            <button
              type="button"
              className="icon-switch"
              disabled={!history.canRedo}
              onClick={redo}
              aria-label="Redo"
              title="Redo (Ctrl+Shift+Z)"
            >
              <RedoIcon />
            </button>
          </div>
          <ZoomControl
            view={view}
            onZoom={(zoom) => setView((current) => zoomAround(current, zoom))}
            onFit={() => setView(FIT_VIEW)}
          />
        </div>
        <button type="button" className="button button-primary" onClick={exportSvg}>
          Export SVG
        </button>
      </div>

      <div className="editor-workspace">
        <LayersPanel
          layers={layers}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onToggleLayer={(id) => update((current) => toggleLayer(current, id))}
          onTogglePart={(layerId, partId) => update((current) => togglePart(current, layerId, partId))}
          onReorder={reorderLayer}
        />
        <EditorCanvas
          canvas={drawing.canvas}
          layers={layers}
          selectedId={selectedId}
          view={view}
          onSelect={setSelectedId}
          onMove={(id, x, y) => changeLayer(id, { x, y }, 'move')}
          onViewChange={setView}
        />
        <PropertiesPanel
          canvas={drawing.canvas}
          layers={layers}
          layer={selected}
          onChange={changeLayer}
          onReorder={reorderLayer}
        />
      </div>

      <label className="talk-bar">
        <span className="talk-badge" aria-hidden="true">
          <SparkleIcon />
          AI
        </span>
        <input
          className="talk-input"
          type="text"
          disabled
          placeholder="Talk to the drawing: “make the roof red” · coming soon"
          aria-label="Talk to the drawing"
        />
      </label>
    </main>
  )
}

function useAutosave(layers: EditorLayer[], drawingId: string, onSave: SaveLayers): void {
  const saved = useRef(layers)
  const pending = useRef<EditorLayer[] | null>(null)

  useEffect(() => {
    if (layers === saved.current) return
    pending.current = layers
    const timer = window.setTimeout(() => {
      saved.current = layers
      pending.current = null
      onSave(drawingId, savedLayerMarkups(layers))
    }, AUTOSAVE_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [layers, drawingId, onSave])

  useEffect(
    () => () => {
      if (pending.current) onSave(drawingId, savedLayerMarkups(pending.current))
    },
    [drawingId, onSave],
  )
}

export default EditorPage
