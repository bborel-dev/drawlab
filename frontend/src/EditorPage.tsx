import { useState } from 'react'
import EditorCanvas from './EditorCanvas'
import {
  editedSvgDocument,
  moveLayerTo,
  parseLayers,
  togglePart,
  updateLayer,
  type EditorLayer,
  type LayerPatch,
} from './editorLayers'
import { downloadSvg, svgFileName, type Drawing } from './layers'
import LayersPanel from './LayersPanel'
import PropertiesPanel from './PropertiesPanel'
import ZoomControl from './ZoomControl'

type EditorPageProps = {
  drawing: Drawing
}

function EditorPage({ drawing }: EditorPageProps) {
  const [layers, setLayers] = useState<EditorLayer[]>(() => parseLayers(drawing.layers))
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [zoom, setZoom] = useState(1)
  const selected = layers.find((layer) => layer.id === selectedId) ?? null

  function changeLayer(id: string, patch: LayerPatch) {
    setLayers((current) => updateLayer(current, id, patch))
  }

  function toggleLayer(id: string) {
    setLayers((current) => current.map((layer) => (layer.id === id ? { ...layer, visible: !layer.visible } : layer)))
  }

  function reorderLayer(id: string, index: number) {
    setLayers((current) => moveLayerTo(current, id, index))
  }

  function exportSvg() {
    downloadSvg(editedSvgDocument(drawing.canvas, layers), svgFileName(drawing.sourceName))
  }

  return (
    <main className="editor glass">
      <div className="converter-row">
        <div className="file-info">
          <span className="file-name">{drawing.sourceName}</span>
          <span className="badge badge-neutral">{layers.length} layers</span>
        </div>
        <ZoomControl zoom={zoom} onChange={setZoom} />
        <button type="button" className="button button-primary" onClick={exportSvg}>
          Export SVG
        </button>
      </div>

      <div className="editor-workspace">
        <LayersPanel
          layers={layers}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onToggleLayer={toggleLayer}
          onTogglePart={(layerId, partId) => setLayers((current) => togglePart(current, layerId, partId))}
          onReorder={reorderLayer}
        />
        <EditorCanvas
          canvas={drawing.canvas}
          layers={layers}
          selectedId={selectedId}
          zoom={zoom}
          onSelect={setSelectedId}
          onMove={(id, x, y) => changeLayer(id, { x, y })}
        />
        <PropertiesPanel
          canvas={drawing.canvas}
          layers={layers}
          layer={selected}
          onChange={changeLayer}
          onReorder={reorderLayer}
        />
      </div>

      <input
        className="talk-input"
        type="text"
        disabled
        placeholder="Talk to the drawing: “make the roof red” · coming soon"
        aria-label="Talk to the drawing"
      />
    </main>
  )
}

export default EditorPage
