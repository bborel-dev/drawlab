import { useRef, useState, type MouseEvent, type PointerEvent } from 'react'

const DRAG_THRESHOLD_PX = 4
const ROW_ATTRIBUTE = 'data-layer-row'

type Press = {
  id: string
  x: number
  y: number
  dragging: boolean
  targetId: string | null
}

export function useLayerDrag(onDrop: (draggedId: string, targetId: string) => void) {
  const press = useRef<Press | null>(null)
  const justDragged = useRef(false)
  const [draggedId, setDraggedId] = useState<string | null>(null)
  const [dropTargetId, setDropTargetId] = useState<string | null>(null)

  function onRowPointerDown(id: string, event: PointerEvent<HTMLElement>) {
    if (event.button !== 0 || (event.target as Element).closest('input')) return
    press.current = { id, x: event.clientX, y: event.clientY, dragging: false, targetId: null }
  }

  function onPointerMove(event: PointerEvent<HTMLElement>) {
    const current = press.current
    if (!current) return
    if (!current.dragging) {
      if (Math.hypot(event.clientX - current.x, event.clientY - current.y) < DRAG_THRESHOLD_PX) return
      current.dragging = true
      event.currentTarget.setPointerCapture(event.pointerId)
      setDraggedId(current.id)
    }
    const row = document.elementFromPoint(event.clientX, event.clientY)?.closest(`[${ROW_ATTRIBUTE}]`)
    current.targetId = row?.getAttribute(ROW_ATTRIBUTE) ?? null
    setDropTargetId(current.targetId)
  }

  function onPointerUp() {
    const current = press.current
    if (current?.dragging && current.targetId && current.targetId !== current.id) onDrop(current.id, current.targetId)
    justDragged.current = Boolean(current?.dragging)
    press.current = null
    setDraggedId(null)
    setDropTargetId(null)
  }

  function onClickCapture(event: MouseEvent<HTMLElement>) {
    if (!justDragged.current) return
    justDragged.current = false
    event.stopPropagation()
    event.preventDefault()
  }

  return {
    draggedId,
    dropTargetId,
    rowProps: (id: string) => ({
      [ROW_ATTRIBUTE]: id,
      onPointerDown: (event: PointerEvent<HTMLElement>) => onRowPointerDown(id, event),
    }),
    listProps: { onPointerMove, onPointerUp, onPointerCancel: onPointerUp, onClickCapture },
  }
}
