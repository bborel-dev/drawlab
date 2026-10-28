import { useCallback, useEffect, useRef, useState } from 'react'

const MERGE_WINDOW_MS = 1000

type Timeline<T> = {
  past: T[]
  present: T
  future: T[]
}

type LastChange = {
  key: string
  time: number
}

export type History<T> = {
  present: T
  canUndo: boolean
  canRedo: boolean
  update: (change: (current: T) => T, mergeKey?: string) => void
  undo: () => void
  redo: () => void
}

export function useHistory<T>(initial: () => T): History<T> {
  const [timeline, setTimeline] = useState<Timeline<T>>(() => ({ past: [], present: initial(), future: [] }))
  const lastChange = useRef<LastChange | null>(null)

  const update = useCallback((change: (current: T) => T, mergeKey?: string) => {
    const now = performance.now()
    const last = lastChange.current
    const merge = mergeKey !== undefined && last?.key === mergeKey && now - last.time < MERGE_WINDOW_MS
    lastChange.current = mergeKey === undefined ? null : { key: mergeKey, time: now }
    setTimeline((current) => {
      const next = change(current.present)
      if (next === current.present) return current
      const past = merge ? current.past : [...current.past, current.present]
      return { past, present: next, future: [] }
    })
  }, [])

  const undo = useCallback(() => {
    lastChange.current = null
    setTimeline((current) => {
      if (current.past.length === 0) return current
      return {
        past: current.past.slice(0, -1),
        present: current.past[current.past.length - 1],
        future: [current.present, ...current.future],
      }
    })
  }, [])

  const redo = useCallback(() => {
    lastChange.current = null
    setTimeline((current) => {
      if (current.future.length === 0) return current
      return {
        past: [...current.past, current.present],
        present: current.future[0],
        future: current.future.slice(1),
      }
    })
  }, [])

  return {
    present: timeline.present,
    canUndo: timeline.past.length > 0,
    canRedo: timeline.future.length > 0,
    update,
    undo,
    redo,
  }
}

export function useUndoShortcuts(active: boolean, undo: () => void, redo: () => void): void {
  useEffect(() => {
    if (!active) return
    function onKeyDown(event: KeyboardEvent) {
      if (!(event.ctrlKey || event.metaKey) || event.altKey || isTextField(event.target)) return
      const key = event.key.toLowerCase()
      const isRedo = (key === 'z' && event.shiftKey) || key === 'y'
      if (key !== 'z' && !isRedo) return
      event.preventDefault()
      if (isRedo) redo()
      else undo()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [active, undo, redo])
}

function isTextField(target: EventTarget | null): boolean {
  if (target instanceof HTMLTextAreaElement) return true
  return target instanceof HTMLInputElement && target.type !== 'range'
}
