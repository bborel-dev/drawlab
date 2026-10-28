import { useState, type DragEvent } from 'react'
import { layerColors, type EditorLayer, type LayerPart } from './editorLayers'
import { ChevronIcon, EyeIcon } from './icons'

type LayersPanelProps = {
  layers: EditorLayer[]
  selectedId: string | null
  onSelect: (id: string) => void
  onToggleLayer: (id: string) => void
  onTogglePart: (layerId: string, partId: string) => void
  onReorder: (id: string, index: number) => void
}

function LayersPanel({ layers, selectedId, onSelect, onToggleLayer, onTogglePart, onReorder }: LayersPanelProps) {
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set())
  const [draggedId, setDraggedId] = useState<string | null>(null)
  const [dropTargetId, setDropTargetId] = useState<string | null>(null)

  function toggleExpanded(id: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (!next.delete(id)) next.add(id)
      return next
    })
  }

  function endDrag() {
    setDraggedId(null)
    setDropTargetId(null)
  }

  function dropOn(targetId: string) {
    if (draggedId) onReorder(draggedId, layers.findIndex((layer) => layer.id === targetId))
    endDrag()
  }

  return (
    <aside className="editor-panel" aria-label="Layers">
      <h2 className="panel-title">
        Layers <span className="panel-count">{layers.length}</span>
      </h2>
      <ul className="layer-list">
        {[...layers].reverse().map((layer) => (
          <li
            key={layer.id}
            draggable
            onDragStart={(event: DragEvent) => {
              event.dataTransfer.effectAllowed = 'move'
              event.dataTransfer.setData('text/plain', layer.id)
              setDraggedId(layer.id)
            }}
            onDragOver={(event: DragEvent) => {
              event.preventDefault()
              setDropTargetId(layer.id)
            }}
            onDrop={(event: DragEvent) => {
              event.preventDefault()
              dropOn(layer.id)
            }}
            onDragEnd={endDrag}
          >
            <div className={layerRowClass(layer, selectedId, draggedId, dropTargetId)}>
              <button
                type="button"
                className={`icon-button chevron${expanded.has(layer.id) ? ' is-open' : ''}`}
                aria-label={`${expanded.has(layer.id) ? 'Collapse' : 'Expand'} ${layer.id}`}
                aria-expanded={expanded.has(layer.id)}
                onClick={() => toggleExpanded(layer.id)}
              >
                <ChevronIcon />
              </button>
              <Swatch color={layerColors(layer)[0]} />
              <button type="button" className="layer-name" onClick={() => onSelect(layer.id)}>
                {layer.id}
              </button>
              <VisibilityButton
                visible={layer.visible}
                label={layer.id}
                onToggle={() => onToggleLayer(layer.id)}
              />
            </div>
            {expanded.has(layer.id) && (
              <ul className="part-list">
                {layer.parts.map((part) => (
                  <PartRow key={part.id} part={part} onToggle={() => onTogglePart(layer.id, part.id)} />
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </aside>
  )
}

function layerRowClass(
  layer: EditorLayer,
  selectedId: string | null,
  draggedId: string | null,
  dropTargetId: string | null,
): string {
  const states = [
    layer.id === selectedId && 'is-selected',
    !layer.visible && 'is-hidden',
    layer.id === draggedId && 'is-dragged',
    layer.id === dropTargetId && layer.id !== draggedId && 'is-drop-target',
  ]
  return ['layer-row', ...states.filter(Boolean)].join(' ')
}

function PartRow({ part, onToggle }: { part: LayerPart; onToggle: () => void }) {
  return (
    <li className={`part-row${part.visible ? '' : ' is-hidden'}`}>
      <Swatch color={part.colors[0]} />
      <span className="part-name">{part.kind === 'ink' ? 'Ink' : 'Color'}</span>
      <span className="part-count">
        {part.colors.length} {part.colors.length === 1 ? 'tone' : 'tones'}
      </span>
      <VisibilityButton visible={part.visible} label={part.id} onToggle={onToggle} />
    </li>
  )
}

function Swatch({ color }: { color: string | undefined }) {
  return <span className="swatch" style={{ background: color ?? 'transparent' }} aria-hidden="true" />
}

type VisibilityButtonProps = {
  visible: boolean
  label: string
  onToggle: () => void
}

function VisibilityButton({ visible, label, onToggle }: VisibilityButtonProps) {
  return (
    <button
      type="button"
      className="icon-button visibility"
      aria-label={`${visible ? 'Hide' : 'Show'} ${label}`}
      aria-pressed={!visible}
      onClick={onToggle}
    >
      <EyeIcon open={visible} />
    </button>
  )
}

export default LayersPanel
