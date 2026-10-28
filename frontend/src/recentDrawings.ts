import { useCallback, useEffect, useRef, useState } from 'react'
import type { Drawing } from './layers'

export type RecentDrawing = {
  id: string
  updatedAt: number
  drawing: Drawing
}

export type RecentDrawings = {
  items: RecentDrawing[]
  add: (drawing: Drawing) => string
  saveLayers: (id: string, layers: string[]) => void
  remove: (id: string) => void
}

const DATABASE_NAME = 'drawlab'
const STORE_NAME = 'recent-drawings'
const MAX_RECENT = 8

export function useRecentDrawings(): RecentDrawings {
  const [items, setItems] = useState<RecentDrawing[]>([])
  const ids = useRef(new WeakMap<Drawing, string>())

  useEffect(() => {
    let cancelled = false
    readAll()
      .then((stored) => {
        if (!cancelled) setItems((current) => newestFirst([...current, ...stored]))
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  const add = useCallback((drawing: Drawing) => {
    const known = ids.current.get(drawing)
    if (known) return known
    const item: RecentDrawing = { id: crypto.randomUUID(), updatedAt: Date.now(), drawing }
    ids.current.set(drawing, item.id)
    setItems((current) => {
      const next = newestFirst([item, ...current])
      next.slice(MAX_RECENT).forEach((dropped) => deleteOne(dropped.id).catch(() => undefined))
      return next.slice(0, MAX_RECENT)
    })
    writeOne(item).catch(() => undefined)
    return item.id
  }, [])

  const saveLayers = useCallback((id: string, layers: string[]) => {
    setItems((current) => {
      const target = current.find((item) => item.id === id)
      if (!target) return current
      const updated = { ...target, updatedAt: Date.now(), drawing: { ...target.drawing, layers } }
      writeOne(updated).catch(() => undefined)
      return newestFirst(current.map((item) => (item.id === id ? updated : item)))
    })
  }, [])

  const remove = useCallback((id: string) => {
    setItems((current) => current.filter((item) => item.id !== id))
    deleteOne(id).catch(() => undefined)
  }, [])

  return { items, add, saveLayers, remove }
}

function newestFirst(items: RecentDrawing[]): RecentDrawing[] {
  const unique = new Map(items.map((item) => [item.id, item]))
  return [...unique.values()].sort((a, b) => b.updatedAt - a.updatedAt)
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, 1)
    request.onupgradeneeded = () => request.result.createObjectStore(STORE_NAME, { keyPath: 'id' })
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

async function withStore<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const database = await openDatabase()
  try {
    return await new Promise<T>((resolve, reject) => {
      const request = run(database.transaction(STORE_NAME, mode).objectStore(STORE_NAME))
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error)
    })
  } finally {
    database.close()
  }
}

function readAll(): Promise<RecentDrawing[]> {
  return withStore('readonly', (store) => store.getAll() as IDBRequest<RecentDrawing[]>)
}

function writeOne(item: RecentDrawing): Promise<IDBValidKey> {
  return withStore('readwrite', (store) => store.put(item))
}

function deleteOne(id: string): Promise<undefined> {
  return withStore('readwrite', (store) => store.delete(id))
}
