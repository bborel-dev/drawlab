import type { Canvas } from './api'
import type { Drawing } from './layers'

export type ImportedSvg = {
  drawing: Drawing
  drawnByDrawlab: boolean
}

const SVG_NAMESPACE = 'http://www.w3.org/2000/svg'
const UNSAFE_ELEMENTS = 'script, foreignObject, iframe, object, embed'
const SHARED_ELEMENTS = new Set(['defs', 'style'])
const IGNORED_ELEMENTS = new Set(['title', 'desc', 'metadata'])
const TAG_NAMES: Record<string, string> = { g: 'group', a: 'link' }
const FALLBACK_SIZE = 1024

export function importSvg(text: string, fileName: string): ImportedSvg {
  const root = new DOMParser().parseFromString(text, 'image/svg+xml').documentElement
  if (root.namespaceURI !== SVG_NAMESPACE || root.localName !== 'svg') {
    throw new Error('This file is not a valid SVG.')
  }
  removeUnsafeContent(root)
  const canvas = svgCanvas(root)
  const drawnByDrawlab = isDrawlabSvg(root)
  const layers = drawnByDrawlab ? drawlabLayers(root) : foreignLayers(root)
  if (layers.length === 0) throw new Error('This SVG has nothing to draw.')
  return { drawing: { canvas, layers, sourceName: fileName }, drawnByDrawlab }
}

function removeUnsafeContent(root: Element): void {
  root.querySelectorAll(UNSAFE_ELEMENTS).forEach((element) => element.remove())
  for (const element of [root, ...root.querySelectorAll('*')]) {
    for (const attribute of [...element.attributes]) {
      if (isUnsafeAttribute(attribute)) element.removeAttributeNode(attribute)
    }
  }
}

function isUnsafeAttribute(attribute: Attr): boolean {
  const name = attribute.name.toLowerCase()
  if (name.startsWith('on')) return true
  return name.endsWith('href') && attribute.value.trim().toLowerCase().startsWith('javascript:')
}

function svgCanvas(root: Element): Canvas {
  const [, , width, height] = viewBox(root)
  return {
    width: Math.round(width || length(root, 'width') || FALLBACK_SIZE),
    height: Math.round(height || length(root, 'height') || FALLBACK_SIZE),
  }
}

function viewBox(root: Element): number[] {
  const values = (root.getAttribute('viewBox') ?? '').trim().split(/[\s,]+/).map(Number)
  return values.length === 4 && values.every(Number.isFinite) ? values : [0, 0, 0, 0]
}

function length(root: Element, attribute: string): number {
  const value = parseFloat(root.getAttribute(attribute) ?? '')
  return Number.isFinite(value) ? value : 0
}

function isDrawlabSvg(root: Element): boolean {
  const groups = [...root.children]
  return (
    groups.length > 0 &&
    groups.every(
      (group) =>
        group.localName === 'g' &&
        group.id !== '' &&
        group.children.length > 0 &&
        [...group.children].every((part) => part.hasAttribute('data-pass')),
    )
  )
}

function drawlabLayers(root: Element): string[] {
  return [...root.children].map((group) => group.outerHTML)
}

function foreignLayers(root: Element): string[] {
  const [minX, minY] = viewBox(root)
  const offset = minX || minY ? ` transform="translate(${-minX},${-minY})"` : ''
  const children = [...root.children]
  const sharedMarkup = children
    .filter((element) => SHARED_ELEMENTS.has(element.localName))
    .map((element) => element.outerHTML)
    .join('')
  const drawn = children.filter((element) => !SHARED_ELEMENTS.has(element.localName) && !IGNORED_ELEMENTS.has(element.localName))
  const source = root.outerHTML
  const taken = new Set([...root.querySelectorAll('[id]')].map((element) => element.id))
  const tagCounts = new Map<string, number>()
  return drawn.map((element, index) => {
    const ownId = element.id
    if (ownId && !source.includes(`#${ownId}`)) {
      element.removeAttribute('id')
      taken.delete(ownId)
    }
    const name = uniqueName(layerBaseName(element, ownId, tagCounts), taken)
    const prefix = index === 0 ? sharedMarkup : ''
    return `<g id="${name}"><g id="${name}-color" data-pass="color"${offset}>${prefix}${element.outerHTML}</g></g>`
  })
}

function layerBaseName(element: Element, ownId: string, tagCounts: Map<string, number>): string {
  const label = ownId || element.getAttribute('inkscape:label')
  if (label) {
    const slug = label.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
    if (slug) return slug
  }
  const tag = TAG_NAMES[element.localName] ?? element.localName
  const count = (tagCounts.get(tag) ?? 0) + 1
  tagCounts.set(tag, count)
  return `${tag}-${count}`
}

function uniqueName(base: string, taken: Set<string>): string {
  let name = base
  for (let count = 2; taken.has(name); count += 1) name = `${base}-${count}`
  taken.add(name)
  return name
}
