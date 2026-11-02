import type { EditPlan, LayerSummary } from './drawingEdits'

export type AgentName = 'art-director' | 'cutter' | 'illustrator'

export type AgentStatus = 'working' | 'done' | 'error'

export type Canvas = {
  width: number
  height: number
}

export type MaskOutline = {
  name: string
  path: string
  width: number
  height: number
}

export type AgentEvent = {
  agent: AgentName
  status: AgentStatus
  message: string
  layer: string | null
  canvas: Canvas | null
  mask: MaskOutline | null
}

export type EditRequest = {
  prompt: string
  svg: string
  layers: LayerSummary[]
  selected: string | null
}

const EVENT_SEPARATOR = '\n\n'
const DATA_PREFIX = 'data: '

export type RepaintRequest = {
  svg: string
  image_prompt: string
  layer_names: string[]
}

export async function streamDrawing(
  image: File,
  onEvent: (event: AgentEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const body = new FormData()
  body.append('image', image)
  const response = await fetch('/api/draw', { method: 'POST', body, signal })
  await readEvents(response, onEvent)
}

export async function streamRepaint(
  body: RepaintRequest,
  onEvent: (event: AgentEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch('/api/repaint', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  await readEvents(response, onEvent)
}

async function readEvents(response: Response, onEvent: (event: AgentEvent) => void): Promise<void> {
  if (!response.ok || !response.body) {
    throw new Error(`Drawing failed (${response.status})`)
  }
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) return
    buffer += value
    const messages = buffer.split(EVENT_SEPARATOR)
    buffer = messages.pop() ?? ''
    messages.forEach((message) => onEvent(parseEvent(message)))
  }
}

function parseEvent(message: string): AgentEvent {
  return JSON.parse(message.slice(DATA_PREFIX.length)) as AgentEvent
}

export async function requestEdit(body: EditRequest, signal: AbortSignal): Promise<EditPlan> {
  const response = await fetch('/api/edit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok) throw new Error(`Edit failed (${response.status})`)
  return (await response.json()) as EditPlan
}
