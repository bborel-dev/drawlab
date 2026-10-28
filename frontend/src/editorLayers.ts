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

const TRANSLATE_PATTERN = /translate\(\s*(-?[\d.]+)[\s,]+(-?[\d.]+)\s*\)/

function parseLayer(markup: string): EditorLayer {
  const group = parseGroup(markup)
  const [x, y] = group ? translation(group) : [0, 0]
  return {
    id: group?.id || layerName(markup),
    parts: group ? Array.from(group.children).map(toPart) : [],
    visible: !group || isShown(group),
    x,
    y,
    opacity: Number(group?.getAttribute('opacity') ?? 1),
  }
}

function translation(group: Element): [number, number] {
  const match = group.getAttribute('transform')?.match(TRANSLATE_PATTERN)
  return match ? [Number(match[1]), Number(match[2])] : [0, 0]
}

function isShown(element: Element): boolean {
  return element.getAttribute('display') !== 'none'
}

function parseGroup(markup: string): Element | null {
  const template = document.createElement('template')
  template.innerHTML = `<svg>${markup}</svg>`
  return template.content.firstElementChild?.firstElementChild ?? null
}

function toPart(element: Element, index: number): LayerPart {
  const visible = isShown(element)
  element.removeAttribute('display')
  return {
    id: element.id || `part-${index + 1}`,
    kind: element.getAttribute('data-pass') ?? 'color',
    markup: element.outerHTML,
    colors: colorsByFrequency(element),
    visible,
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
  const target = layers.find((layer) => layer.id === id)
  if (!target || !changesLayer(target, patch)) return layers
  return layers.map((layer) => (layer === target ? { ...layer, ...patch } : layer))
}

function changesLayer(layer: EditorLayer, patch: LayerPatch): boolean {
  return (Object.keys(patch) as (keyof LayerPatch)[]).some((key) => patch[key] !== layer[key])
}

export function toggleLayer(layers: EditorLayer[], id: string): EditorLayer[] {
  return layers.map((layer) => (layer.id === id ? { ...layer, visible: !layer.visible } : layer))
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
  return svgDocument(canvas, layers.filter((layer) => layer.visible).map(exportedLayerMarkup))
}

export function savedLayerMarkups(layers: EditorLayer[]): string[] {
  return layers.map(savedLayerMarkup)
}

function exportedLayerMarkup(layer: EditorLayer): string {
  const parts = layer.parts.filter((part) => part.visible).map((part) => part.markup)
  return `<g id="${layer.id}"${layerAttributes(layer)}>${parts.join('')}</g>`
}

function savedLayerMarkup(layer: EditorLayer): string {
  const parts = layer.parts.map((part) => (part.visible ? part.markup : hiddenMarkup(part.markup)))
  const display = layer.visible ? '' : ' display="none"'
  return `<g id="${layer.id}"${layerAttributes(layer)}${display}>${parts.join('')}</g>`
}

function hiddenMarkup(markup: string): string {
  return markup.replace(/^<(\w+)/, '<$1 display="none"')
}

function layerAttributes(layer: EditorLayer): string {
  const transform = layerTransform(layer)
  const transformAttribute = transform ? ` transform="${transform}"` : ''
  const opacityAttribute = layer.opacity < 1 ? ` opacity="${layer.opacity}"` : ''
  return transformAttribute + opacityAttribute
}
