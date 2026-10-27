import { useRef, useState, type ChangeEvent, type DragEvent } from 'react'

type DropZoneProps = {
  onFile: (file: File) => void
}

const ACCEPTED_TYPES = 'image/png,image/jpeg,image/webp'

function DropZone({ onFile }: DropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isOver, setIsOver] = useState(false)

  function handleDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault()
    setIsOver(false)
    const file = event.dataTransfer.files[0]
    if (file) onFile(file)
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (file) onFile(file)
  }

  return (
    <section
      className={`drop-zone${isOver ? ' is-over' : ''}`}
      aria-label="Upload an image"
      onDragOver={(event) => {
        event.preventDefault()
        setIsOver(true)
      }}
      onDragLeave={() => setIsOver(false)}
      onDrop={handleDrop}
    >
      <span className="drop-icon" aria-hidden="true">
        <svg width="20" height="20" viewBox="0 0 24 24">
          <path
            d="M12 16 V5 M7 10 L12 5 L17 10 M5 19 H19"
            fill="none"
            stroke="#1C1E21"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <p className="drop-title">Drop an image here</p>
      <button type="button" className="button button-primary" onClick={() => inputRef.current?.click()}>
        Choose a file
      </button>
      <input ref={inputRef} type="file" accept={ACCEPTED_TYPES} hidden onChange={handleChange} />
      <p className="drop-hint">PNG, JPG or WebP, up to 10 MB</p>
    </section>
  )
}

export default DropZone
