export type TalkStage = 'planning' | 'repainting'

type Durations = Partial<Record<TalkStage, number>>

const DEFAULT_DURATION_MS: Record<TalkStage, number> = { planning: 8_000, repainting: 90_000 }
const STORAGE_KEY = 'drawlab.talk-durations'
const LEARNING_RATE = 0.5

export function expectedDuration(stage: TalkStage): number {
  return readDurations()[stage] ?? DEFAULT_DURATION_MS[stage]
}

export function recordDuration(stage: TalkStage, durationMs: number): void {
  const durations = readDurations()
  const previous = durations[stage] ?? DEFAULT_DURATION_MS[stage]
  writeDurations({ ...durations, [stage]: previous + (durationMs - previous) * LEARNING_RATE })
}

export function formatDuration(durationMs: number): string {
  const seconds = Math.max(0, Math.round(durationMs / 1000))
  const minutes = Math.floor(seconds / 60)
  return minutes > 0 ? `${minutes}:${String(seconds % 60).padStart(2, '0')}` : `${seconds}s`
}

function readDurations(): Durations {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') as Durations
  } catch {
    return {}
  }
}

function writeDurations(durations: Durations): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(durations))
  } catch {
    return
  }
}
