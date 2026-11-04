type Example = {
  file: string
  label: string
}

const EXAMPLES: Example[] = [
  { file: 'flower.jpg', label: 'Potted plant' },
  { file: 'dance.jpg', label: 'Dancing couple' },
]

type ExampleImagesProps = {
  onFile: (file: File) => void
  title?: string
}

async function loadExample(example: Example): Promise<File> {
  const response = await fetch(`/examples/${example.file}`)
  const blob = await response.blob()
  return new File([blob], example.file, { type: blob.type || 'image/jpeg' })
}

function ExampleImages({ onFile, title = 'Or try an example' }: ExampleImagesProps) {
  async function pick(example: Example) {
    onFile(await loadExample(example))
  }

  return (
    <section className="examples" aria-label="Example images">
      <p className="examples-title">{title}</p>
      <div className="examples-row">
        {EXAMPLES.map((example) => (
          <button
            key={example.file}
            type="button"
            className="example-card"
            onClick={() => void pick(example)}
            title={example.label}
          >
            <img src={`/examples/${example.file}`} alt={example.label} loading="lazy" />
          </button>
        ))}
      </div>
    </section>
  )
}

export default ExampleImages
