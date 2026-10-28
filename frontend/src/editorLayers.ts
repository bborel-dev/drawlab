import type { Canvas } from './api'
import { layerName, svgDocument } from './layers'

export type LayerPart = {
  id: string
  kind: string
  markup: string
  colors: string[]
  visible: boolean
}

export type EditorLayer = {
  id: string
  parts: LayerPart[]
  visible: boolean
  x: number
  y: number
  opacity: number
}

export type LayerPatch = Partial<Pick<EditorLayer, 'visible' | 'x' | 'y' | 'opacity'>>

export function parseLayers(markups: string[]): EditorLayer[] {
  return markups.map(parseLayer)
}

function parseLayer(markup: string): EditorLayer {
  const group = parseGroup(markup)
  return {
    id: group?.id || layerName(markup),
    parts: group ? Array.from(group.children).map(toPart) : [],
    visible: true,
    x: 0,
    y: 0,
    opacity: 1,
  }
}

function parseGroup(markup: string): Element | null {
  const template = document.createElement('template')
  template.innerHTML = `<svg>${markup}</svg>`
  return template.content.firstElementChild?.firstElementChild ?? null
}

function toPart(element: Element, index: number): LayerPart {
  return {
    id: element.id || `part-${index + 1}`,
    kind: element.getAttribute('data-pass') ?? 'color',
    markup: element.outerHTML,
    colors: colorsByFrequency(element),
    visible: true,
  }
}

function colorsByFrequency(element: Element): string[] {
  const counts = new Map<string, number>()
  element.querySelectorAll('[fill]').forEach((node) => {
    const fill = node.getAttribute('fill')?.toLowerCase()
    if (fill && fill !== 'none') counts.set(fill, (counts.get(fill) ?? 0) + 1)
  })
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).map(([color]) => color)
}

export function layerColors(layer: EditorLayer): string[] {
  return [...new Set(layer.parts.flatMap((part) => part.colors))]
}

export function updateLayer(layers: EditorLayer[], id: string, patch: LayerPatch): EditorLayer[] {
  return layers.map((layer) => (layer.id === id ? { ...layer, ...patch } : layer))
}

export function togglePart(layers: EditorLayer[], layerId: string, partId: string): EditorLayer[] {
  return layers.map((layer) =>
    layer.id === layerId
      ? {
          ...layer,
          parts: layer.parts.map((part) => (part.id === partId ? { ...part, visible: !part.visible } : part)),
        }
      : layer,
  )
}

export function moveLayerTo(layers: EditorLayer[], id: string, index: number): EditorLayer[] {
  const from = layers.findIndex((layer) => layer.id === id)
  if (from < 0 || index < 0 || index >= layers.length || index === from) return layers
  const next = layers.filter((layer) => layer.id !== id)
  next.splice(index, 0, layers[from])
  return next
}

export function layerTransform(layer: EditorLayer): string | undefined {
  return layer.x || layer.y ? `translate(${layer.x},${layer.y})` : undefined
}

export function editedSvgDocument(canvas: Canvas, layers: EditorLayer[]): string {
  return svgDocument(canvas, layers.filter((layer) => layer.visible).map(layerMarkup))
}

function layerMarkup(layer: EditorLayer): string {
  const parts = layer.parts.filter((part) => part.visible).map((part) => part.markup)
  return `<g id="${layer.id}"${layerAttributes(layer)}>${parts.join('')}</g>`
}

function layerAttributes(layer: EditorLayer): string {
  const transform = layerTransform(layer)
  const transformAttribute = transform ? ` transform="${transform}"` : ''
  const opacityAttribute = layer.opacity < 1 ? ` opacity="${layer.opacity}"` : ''
  return transformAttribute + opacityAttribute
}
