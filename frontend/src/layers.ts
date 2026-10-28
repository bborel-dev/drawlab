import type { Canvas } from './api'

export type Drawing = {
  canvas: Canvas
  layers: string[]
  sourceName: string
}

const LAYER_NAME_PATTERN = /^<g id="([^"]+)"/

export function layerName(markup: string): string {
  return markup.match(LAYER_NAME_PATTERN)?.[1] ?? 'layer'
}

export function svgDocument(canvas: Canvas, layers: string[]): string {
  const { width, height } = canvas
  return (
    `<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" ` +
    `viewBox="0 0 ${width} ${height}">${layers.join('')}</svg>`
  )
}

export function downloadSvg(svg: string, fileName: string): void {
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }))
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  link.click()
  URL.revokeObjectURL(url)
}

export function svgFileName(sourceName: string): string {
  return `${sourceName.replace(/\.[^.]+$/, '')}.svg`
}
