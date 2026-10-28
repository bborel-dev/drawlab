import type { Canvas } from './api'
import { layerColors, type EditorLayer, type LayerPatch } from './editorLayers'

type PropertiesPanelProps = {
  canvas: Canvas
  layers: EditorLayer[]
  layer: EditorLayer | null
  onChange: (id: string, patch: LayerPatch) => void
  onReorder: (id: string, index: number) => void
}

const MAX_SHOWN_COLORS = 8

function PropertiesPanel({ canvas, layers, layer, onChange, onReorder }: PropertiesPanelProps) {
  if (!layer) {
    return (
      <aside className="editor-panel" aria-label="Properties">
        <h2 className="panel-title">Canvas</h2>
        <dl className="prop-facts">
          <dt>Size</dt>
          <dd>
            {canvas.width} × {canvas.height}
          </dd>
          <dt>Layers</dt>
          <dd>{layers.length}</dd>
        </dl>
        <p className="panel-hint">Select a layer on the canvas or in the list to move it.</p>
      </aside>
    )
  }

  const index = layers.indexOf(layer)
  const colors = layerColors(layer)

  return (
    <aside className="editor-panel" aria-label="Properties">
      <h2 className="panel-title panel-title-layer">{layer.id}</h2>

      <section className="prop-section">
        <h3>Position</h3>
        <div className="field-row">
          <NumberField label="X" value={layer.x} onChange={(x) => onChange(layer.id, { x })} />
          <NumberField label="Y" value={layer.y} onChange={(y) => onChange(layer.id, { y })} />
        </div>
        <button
          type="button"
          className="button button-ghost button-small"
          disabled={layer.x === 0 && layer.y === 0}
          onClick={() => onChange(layer.id, { x: 0, y: 0 })}
        >
          Reset position
        </button>
      </section>

      <section className="prop-section">
        <h3>Opacity</h3>
        <div className="opacity-field">
          <input
            type="range"
            min={0}
            max={100}
            value={Math.round(layer.opacity * 100)}
            onChange={(event) => onChange(layer.id, { opacity: Number(event.target.value) / 100 })}
            aria-label="Opacity"
          />
          <span>{Math.round(layer.opacity * 100)}%</span>
        </div>
      </section>

      <section className="prop-section">
        <h3>Arrange</h3>
        <div className="field-row">
          <button
            type="button"
            className="button button-secondary button-small"
            disabled={index === layers.length - 1}
            onClick={() => onReorder(layer.id, index + 1)}
          >
            Forward
          </button>
          <button
            type="button"
            className="button button-secondary button-small"
            disabled={index === 0}
            onClick={() => onReorder(layer.id, index - 1)}
          >
            Backward
          </button>
        </div>
      </section>

      <section className="prop-section">
        <h3>Fills</h3>
        <ul className="fill-list">
          {colors.slice(0, MAX_SHOWN_COLORS).map((color) => (
            <li key={color}>
              <span className="swatch" style={{ background: color }} aria-hidden="true" />
              {color.toUpperCase()}
            </li>
          ))}
        </ul>
        {colors.length > MAX_SHOWN_COLORS && (
          <p className="panel-hint">+{colors.length - MAX_SHOWN_COLORS} more tones</p>
        )}
      </section>
    </aside>
  )
}

type NumberFieldProps = {
  label: string
  value: number
  onChange: (value: number) => void
}

function NumberField({ label, value, onChange }: NumberFieldProps) {
  return (
    <label className="number-field">
      <span>{label}</span>
      <input
        type="number"
        value={value}
        onChange={(event) => {
          const next = event.target.valueAsNumber
          if (Number.isFinite(next)) onChange(next)
        }}
      />
    </label>
  )
}

export default PropertiesPanel
