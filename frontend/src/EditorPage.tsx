import { useEffect, useRef, useState } from 'react'
import { requestEdit, streamRepaint } from './api'
import { applyEditPlan, changedLayers, shownLayers, summarizeLayers, type EditPlan } from './drawingEdits'
import EditorCanvas, { type Redraw } from './EditorCanvas'
import {
  availableLayerId,
  deleteLayer,
  duplicateLayer,
  editedSvgDocument,
  moveLayerTo,
  parseLayers,
  recolorFamily,
  renameLayer,
  savedLayerMarkups,
  toggleLayer,
  togglePart,
  updateLayer,
  withBackgroundLayer,
  type EditorLayer,
  type LayerPatch,
} from './editorLayers'
import { BackIcon, RedoIcon, UndoIcon } from './icons'
import { downloadSvg, svgFileName, type Drawing } from './layers'
import LayersPanel from './LayersPanel'
import PropertiesPanel from './PropertiesPanel'
import TalkBar, { type TalkAnswer, type TalkProgress } from './TalkBar'
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
  const history = useHistory(() => withBackgroundLayer(parseLayers(drawing.layers), drawing.canvas))
  const { present: layers, update, undo, redo } = history
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [view, setView] = useState<View>(FIT_VIEW)
  const [redraw, setRedraw] = useState<Redraw | null>(null)
  const editRequest = useRef<AbortController | null>(null)
  const redrawCount = useRef(0)
  const selected = layers.find((layer) => layer.id === selectedId) ?? null
  useUndoShortcuts(active, undo, redo)
  useAutosave(layers, drawingId, onSave)
  useEffect(() => () => editRequest.current?.abort(), [])

  function changeLayer(id: string, patch: LayerPatch, gesture?: string) {
    update((current) => updateLayer(current, id, patch), gesture && `${gesture}:${id}`)
  }

  function reorderLayer(id: string, index: number) {
    update((current) => moveLayerTo(current, id, index))
  }

  function recolorLayer(id: string, family: number, color: string) {
    update((current) => recolorFamily(current, id, family, color), `fill:${id}:${family}`)
  }

  function renameSelected(id: string, name: string) {
    const newId = availableLayerId(name, layers, id)
    update((current) => renameLayer(current, id, newId))
    if (selectedId === id) setSelectedId(newId)
  }

  function duplicate(id: string) {
    const copyId = availableLayerId(`${id}-copy`, layers)
    update((current) => duplicateLayer(current, id, copyId))
    setSelectedId(copyId)
  }

  function remove(id: string) {
    update((current) => deleteLayer(current, id))
    if (selectedId === id) setSelectedId(null)
  }

  async function talkToDrawing(prompt: string, onProgress: (progress: TalkProgress) => void): Promise<TalkAnswer> {
    editRequest.current?.abort()
    const controller = new AbortController()
    editRequest.current = controller
    const svg = editedSvgDocument(drawing.canvas, layers)
    const plan = await requestEdit(
      { prompt, svg, layers: summarizeLayers(layers), selected: selectedId },
      controller.signal,
    )
    if (plan.image_prompt) return repaint(plan, svg, onProgress, controller.signal)
    if (plan.operations.length > 0) {
      update((current) => applyEditPlan(current, plan, drawing.canvas))
      setRedraw({ ids: shownLayers(plan), key: ++redrawCount.current })
    }
    return { reply: plan.reply, changed: changedLayers(plan) }
  }

  async function repaint(
    plan: EditPlan,
    svg: string,
    onProgress: (progress: TalkProgress) => void,
    signal: AbortSignal,
  ): Promise<TalkAnswer> {
    const markups: string[] = []
    let failure: string | null = null
    onProgress({ stage: 'repainting', message: plan.reply })
    await streamRepaint(
      { svg, image_prompt: plan.image_prompt, layer_names: layers.map((layer) => layer.id) },
      (event) => {
        if (event.layer) markups.push(event.layer)
        if (event.status === 'error') failure = event.message
        else onProgress({ stage: 'repainting', message: event.message })
      },
      signal,
    )
    if (failure || markups.length === 0) return { reply: failure ?? 'The scene could not be redrawn.', changed: [] }
    const redrawn = withBackgroundLayer(parseLayers(markups), drawing.canvas)
    update(() => redrawn)
    setSelectedId(null)
    setRedraw({ ids: redrawn.map((layer) => layer.id), key: ++redrawCount.current })
    return { reply: plan.reply, changed: [`all ${redrawn.length} layers redrawn`] }
  }

  function cancelTalk() {
    editRequest.current?.abort()
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
          onRename={renameSelected}
        />
        <EditorCanvas
          canvas={drawing.canvas}
          layers={layers}
          selectedId={selectedId}
          view={view}
          redraw={redraw}
          onSelect={setSelectedId}
          onMove={(id, x, y) => changeLayer(id, { x, y }, 'move')}
          onDelete={remove}
          onViewChange={setView}
        />
        <PropertiesPanel
          canvas={drawing.canvas}
          layers={layers}
          layer={selected}
          onChange={changeLayer}
          onReorder={reorderLayer}
          onRecolor={recolorLayer}
          onDuplicate={duplicate}
          onDelete={remove}
        />
      </div>

      <TalkBar onAsk={talkToDrawing} onCancel={cancelTalk} />
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
