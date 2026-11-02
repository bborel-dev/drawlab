import { createPortal } from 'react-dom'
import { useEscape } from './useEscape'

type ConfirmDialogProps = {
  title: string
  message: string
  confirmLabel: string
  cancelLabel: string
  onConfirm: () => void
  onCancel: () => void
}

function ConfirmDialog({ title, message, confirmLabel, cancelLabel, onConfirm, onCancel }: ConfirmDialogProps) {
  useEscape(onCancel)
  return createPortal(
    <div className="dialog-backdrop" onPointerDown={(event) => event.target === event.currentTarget && onCancel()}>
      <section className="confirm glass" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title">
        <h2 id="confirm-title" className="confirm-title">
          {title}
        </h2>
        <p className="confirm-message">{message}</p>
        <footer className="confirm-actions">
          <button type="button" className="button button-ghost" onClick={onCancel} autoFocus>
            {cancelLabel}
          </button>
          <button type="button" className="button button-primary" onClick={onConfirm}>
            {confirmLabel}
          </button>
        </footer>
      </section>
    </div>,
    document.body,
  )
}

export default ConfirmDialog
