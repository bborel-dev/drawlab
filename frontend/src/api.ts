import type { EditPlan, LayerSummary } from './drawingEdits'

export type AgentName = 'art-director' | 'cutter' | 'completer' | 'illustrator'

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
const API_URL = (import.meta.env.VITE_API_URL ?? '/api').replace(/\/+$/, '')

export class ApiError extends Error {}

export type Allowance = {
  left: number
  limit: number
}

export type Quota = {
  conversions: Allowance
  edits: Allowance
  open: boolean
}

const quotaListeners = new Set<() => void>()

export function onQuotaChange(listener: () => void): () => void {
  quotaListeners.add(listener)
  return () => quotaListeners.delete(listener)
}

function quotaChanged(): void {
  quotaListeners.forEach((listener) => listener())
}

export async function fetchQuota(signal: AbortSignal): Promise<Quota> {
  const response = await fetch(`${API_URL}/quota`, { signal })
  if (!response.ok) throw await failure(response, 'Quota failed')
  return (await response.json()) as Quota
}

export type ProposalRequest = { image_prompt: string } & ({ svg: string } | { image: string })

export type RedrawRequest = {
  image: string
  width: number
  height: number
  layer_names: string[]
}

export async function streamDrawing(
  image: File,
  onEvent: (event: AgentEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const body = new FormData()
  body.append('image', image)
  const response = await fetch(`${API_URL}/draw`, { method: 'POST', body, signal })
  quotaChanged()
  await readEvents(response, onEvent)
}

export async function requestProposal(body: ProposalRequest, signal: AbortSignal): Promise<string> {
  const response = await postJson('/repaint/proposal', body, signal)
  if (!response.ok) throw await failure(response, 'Repaint proposal failed')
  return ((await response.json()) as { image: string }).image
}

export async function streamRepaint(
  body: RedrawRequest,
  onEvent: (event: AgentEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  await readEvents(await postJson('/repaint', body, signal), onEvent)
}

function postJson(path: string, body: unknown, signal: AbortSignal): Promise<Response> {
  return fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
}

async function readEvents(response: Response, onEvent: (event: AgentEvent) => void): Promise<void> {
  if (!response.ok || !response.body) throw await failure(response, 'Drawing failed')
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
  const response = await postJson('/edit', body, signal)
  quotaChanged()
  if (!response.ok) throw await failure(response, 'Edit failed')
  return (await response.json()) as EditPlan
}

async function failure(response: Response, fallback: string): Promise<ApiError> {
  const detail = await response
    .json()
    .then((body: { detail?: unknown }) => body.detail)
    .catch(() => undefined)
  return new ApiError(typeof detail === 'string' ? detail : `${fallback} (${response.status})`)
}
