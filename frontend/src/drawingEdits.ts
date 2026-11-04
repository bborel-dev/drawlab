import type { Canvas } from './api'
import { moveLayerTo, type EditorLayer } from './editorLayers'
import { familyTones, toneFamilies, type Tone } from './tones'

type EditOp = 'hide' | 'show' | 'move' | 'opacity' | 'forward' | 'backward' | 'front' | 'back'

type EditOperation = {
  op: EditOp
  layer: string
  dx: number
  dy: number
  opacity: number
}

export type EditPlan = {
  reply: string
  image_prompt: string
  operations: EditOperation[]
}

export type LayerSummary = {
  id: string
  visible: boolean
  tones: Tone[]
}

export function summarizeLayers(layers: EditorLayer[]): LayerSummary[] {
  return layers.map((layer) => ({
    id: layer.id,
    visible: layer.visible,
    tones: familyTones(toneFamilies(colorMarkups(layer))),
  }))
}

export function changedLayers(plan: EditPlan): string[] {
  return [...new Set(plan.operations.map((operation) => operation.layer))]
}

export function shownLayers(plan: EditPlan): string[] {
  return plan.operations.filter((operation) => operation.op === 'show').map((operation) => operation.layer)
}

export function applyEditPlan(layers: EditorLayer[], plan: EditPlan, canvas: Canvas): EditorLayer[] {
  return plan.operations.reduce((current, operation) => applyOperation(current, operation, canvas), layers)
}

function applyOperation(layers: EditorLayer[], operation: EditOperation, canvas: Canvas): EditorLayer[] {
  const index = layers.findIndex((layer) => layer.id === operation.layer)
  if (index < 0) return layers
  switch (operation.op) {
    case 'forward':
      return moveLayerTo(layers, operation.layer, index + 1)
    case 'backward':
      return moveLayerTo(layers, operation.layer, index - 1)
    case 'front':
      return moveLayerTo(layers, operation.layer, layers.length - 1)
    case 'back':
      return moveLayerTo(layers, operation.layer, 0)
    default:
      return layers.map((layer, position) => (position === index ? editLayer(layer, operation, canvas) : layer))
  }
}

function editLayer(layer: EditorLayer, operation: EditOperation, canvas: Canvas): EditorLayer {
  switch (operation.op) {
    case 'hide':
      return { ...layer, visible: false }
    case 'show':
      return { ...layer, visible: true }
    case 'move':
      return {
        ...layer,
        x: Math.round(layer.x + operation.dx * canvas.width),
        y: Math.round(layer.y + operation.dy * canvas.height),
      }
    case 'opacity':
      return { ...layer, opacity: operation.opacity }
    default:
      return layer
  }
}

function colorMarkups(layer: EditorLayer): string[] {
  return layer.parts.filter((part) => part.kind === 'color').map((part) => part.markup)
}
