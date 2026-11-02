export type TalkStage = 'planning' | 'proposing' | 'reviewing' | 'drawing'

type TimedStage = Exclude<TalkStage, 'reviewing'>

type Durations = Partial<Record<TimedStage, number>>

const DEFAULT_DURATION_MS: Record<TimedStage, number> = { planning: 15_000, proposing: 20_000, drawing: 85_000 }
const STORAGE_KEY = 'drawlab.talk-durations'
const LEARNING_RATE = 0.5

export function isTimed(stage: TalkStage): stage is TimedStage {
  return stage !== 'reviewing'
}

export function expectedDuration(stage: TimedStage): number {
  return readDurations()[stage] ?? DEFAULT_DURATION_MS[stage]
}

export function recordDuration(stage: TimedStage, durationMs: number): void {
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
