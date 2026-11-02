import { useState, type KeyboardEvent } from 'react'
import { layerColors, type EditorLayer, type LayerPart } from './editorLayers'
import { ChevronIcon, EyeIcon } from './icons'
import { useLayerDrag } from './useLayerDrag'

type LayersPanelProps = {
  layers: EditorLayer[]
  selectedId: string | null
  onSelect: (id: string) => void
  onToggleLayer: (id: string) => void
  onTogglePart: (layerId: string, partId: string) => void
  onReorder: (id: string, index: number) => void
  onRename: (id: string, name: string) => void
}

function LayersPanel({
  layers,
  selectedId,
  onSelect,
  onToggleLayer,
  onTogglePart,
  onReorder,
  onRename,
}: LayersPanelProps) {
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set())
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const { draggedId, dropTargetId, rowProps, listProps } = useLayerDrag((id, targetId) =>
    onReorder(id, layers.findIndex((layer) => layer.id === targetId)),
  )

  function toggleExpanded(id: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (!next.delete(id)) next.add(id)
      return next
    })
  }

  return (
    <aside className="editor-panel" aria-label="Layers">
      <h2 className="panel-title">
        Layers <span className="panel-count">{layers.length}</span>
      </h2>
      <ul className="layer-list" {...listProps}>
        {[...layers].reverse().map((layer) => (
          <li key={layer.id} {...rowProps(layer.id)}>
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
              {renamingId === layer.id ? (
                <RenameField
                  name={layer.id}
                  onDone={(name) => {
                    setRenamingId(null)
                    if (name && name !== layer.id) onRename(layer.id, name)
                  }}
                />
              ) : (
                <button
                  type="button"
                  className="layer-name"
                  title="Double-click to rename"
                  onClick={() => onSelect(layer.id)}
                  onDoubleClick={() => setRenamingId(layer.id)}
                >
                  {layer.id}
                </button>
              )}
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

function RenameField({ name, onDone }: { name: string; onDone: (name: string | null) => void }) {
  const [value, setValue] = useState(name)

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') onDone(value.trim())
    if (event.key === 'Escape') onDone(null)
  }

  return (
    <input
      className="layer-rename"
      value={value}
      autoFocus
      aria-label={`Rename ${name}`}
      onChange={(event) => setValue(event.target.value)}
      onKeyDown={onKeyDown}
      onBlur={() => onDone(value.trim())}
    />
  )
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
