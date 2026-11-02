import { useEffect, useRef, useState } from 'react'
import { requestEdit, requestProposal, streamRepaint } from './api'
import ConfirmDialog from './ConfirmDialog'
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
import RepaintProposal, { type Proposal, type ProposalChoice } from './RepaintProposal'
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

type OpenProposal = Proposal & {
  svg: string
  choose: (choice: ProposalChoice) => void
}

const AUTOSAVE_DELAY_MS = 800
const DISCARDED_REPLY = 'The new scene was discarded, the drawing is unchanged.'
const LEAVE_WHILE_EDITING = 'Muse is still working on your edit. Leaving now cancels it and keeps the drawing as it was.'
const LEAVE_WHEN_SAVED = 'Your drawing is saved in this browser. You can reopen it anytime from your drawings.'

function EditorPage({ drawingId, drawing, active, onSave, onBack }: EditorPageProps) {
  const history = useHistory(() => withBackgroundLayer(parseLayers(drawing.layers), drawing.canvas))
  const { present: layers, update, undo, redo } = history
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [view, setView] = useState<View>(FIT_VIEW)
  const [redraw, setRedraw] = useState<Redraw | null>(null)
  const [proposal, setProposal] = useState<OpenProposal | null>(null)
  const [canvasLocked, setCanvasLocked] = useState(false)
  const [talkRunning, setTalkRunning] = useState(false)
  const [leaving, setLeaving] = useState(false)
  const editRequest = useRef<AbortController | null>(null)
  const redrawCount = useRef(0)
  const selected = layers.find((layer) => layer.id === selectedId) ?? null
  useUndoShortcuts(active && !canvasLocked, undo, redo)
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
    setTalkRunning(true)
    try {
      return await runTalk(prompt, onProgress)
    } finally {
      setTalkRunning(false)
    }
  }

  async function runTalk(prompt: string, onProgress: (progress: TalkProgress) => void): Promise<TalkAnswer> {
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
    try {
      const image = await chooseProposal(plan, svg, onProgress, signal)
      if (!image) return { reply: DISCARDED_REPLY, changed: [] }
      setProposal(null)
      return await drawScene(image, plan.reply, onProgress, signal)
    } finally {
      setProposal(null)
    }
  }

  async function chooseProposal(
    plan: EditPlan,
    svg: string,
    onProgress: (progress: TalkProgress) => void,
    signal: AbortSignal,
  ): Promise<string | null> {
    onProgress({ stage: 'proposing', message: 'Muse Image is repainting the scene…' })
    let image = await requestProposal({ svg, image_prompt: plan.image_prompt }, signal)
    let reply = plan.reply
    for (;;) {
      onProgress({ stage: 'reviewing', message: 'Review the new scene, then draw it or retouch it' })
      const choice = await askChoice({ image, reply, busy: false }, svg, signal)
      if (choice.kind === 'accept') return image
      if (choice.kind === 'discard') return null
      setProposal((current) => current && { ...current, busy: true })
      onProgress({ stage: 'proposing', message: 'Muse Image is retouching the scene…' })
      image = await requestProposal({ image, image_prompt: choice.instruction }, signal)
      reply = `Retouched: ${choice.instruction}`
    }
  }

  function askChoice(proposal: Proposal, svg: string, signal: AbortSignal): Promise<ProposalChoice> {
    return new Promise((resolve, reject) => {
      const abort = () => reject(new DOMException('The request was cancelled', 'AbortError'))
      if (signal.aborted) return abort()
      signal.addEventListener('abort', abort, { once: true })
      const choose = (choice: ProposalChoice) => {
        signal.removeEventListener('abort', abort)
        resolve(choice)
      }
      setProposal({ ...proposal, svg, choose })
    })
  }

  async function drawScene(
    image: string,
    reply: string,
    onProgress: (progress: TalkProgress) => void,
    signal: AbortSignal,
  ): Promise<TalkAnswer> {
    const markups: string[] = []
    let failure: string | null = null
    onProgress({ stage: 'drawing', message: 'Drawing the new scene' })
    setSelectedId(null)
    setCanvasLocked(true)
    try {
      await streamRepaint(
        { image, ...drawing.canvas, layer_names: layers.map((layer) => layer.id) },
        (event) => {
          if (event.layer) markups.push(event.layer)
          if (event.status === 'error') failure = event.message
          else onProgress({ stage: 'drawing', message: event.message })
        },
        signal,
      )
    } finally {
      setCanvasLocked(false)
    }
    if (failure || markups.length === 0) return { reply: failure ?? 'The scene could not be redrawn.', changed: [] }
    const redrawn = withBackgroundLayer(parseLayers(markups), drawing.canvas)
    update(() => redrawn)
    setSelectedId(null)
    setRedraw({ ids: redrawn.map((layer) => layer.id), key: ++redrawCount.current })
    return { reply, changed: [`all ${redrawn.length} layers redrawn`] }
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
            onClick={() => setLeaving(true)}
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
              disabled={canvasLocked || !history.canUndo}
              onClick={undo}
              aria-label="Undo"
              title="Undo (Ctrl+Z)"
            >
              <UndoIcon />
            </button>
            <button
              type="button"
              className="icon-switch"
              disabled={canvasLocked || !history.canRedo}
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

      <div className="editor-workspace" inert={canvasLocked}>
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
          locked={canvasLocked}
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
      {proposal && <RepaintProposal proposal={proposal} currentSvg={proposal.svg} onChoose={proposal.choose} />}
      {leaving && (
        <ConfirmDialog
          title="Back to your drawings?"
          message={talkRunning ? LEAVE_WHILE_EDITING : LEAVE_WHEN_SAVED}
          confirmLabel={talkRunning ? 'Cancel the edit and leave' : 'Leave'}
          cancelLabel="Stay"
          onConfirm={onBack}
          onCancel={() => setLeaving(false)}
        />
      )}
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
