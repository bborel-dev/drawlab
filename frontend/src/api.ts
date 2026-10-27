export type AgentName = 'art-director' | 'cutter' | 'illustrator'

export type AgentStatus = 'working' | 'done' | 'error'

export type Canvas = {
  width: number
  height: number
}

export type AgentEvent = {
  agent: AgentName
  status: AgentStatus
  message: string
  layer: string | null
  canvas: Canvas | null
}

const EVENT_SEPARATOR = '\n\n'
const DATA_PREFIX = 'data: '

export async function streamDrawing(
  image: File,
  onEvent: (event: AgentEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const body = new FormData()
  body.append('image', image)
  const response = await fetch('/api/draw', { method: 'POST', body, signal })
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
