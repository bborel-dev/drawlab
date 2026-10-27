type Example = {
  fileName: string
  label: string
  url: string
}

const EXAMPLES: Example[] = [
  { fileName: 'flat-landscape.png', label: 'Landscape example', url: '/examples/flat-landscape.png' },
]

type ExamplesProps = {
  onFile: (file: File) => void
}

function Examples({ onFile }: ExamplesProps) {
  async function pick(example: Example) {
    const blob = await (await fetch(example.url)).blob()
    onFile(new File([blob], example.fileName, { type: blob.type }))
  }

  return (
    <section className="examples" aria-label="Examples">
      <span>Try an example</span>
      {EXAMPLES.map((example) => (
        <button
          key={example.fileName}
          type="button"
          className="example"
          aria-label={example.label}
          onClick={() => pick(example)}
        >
          <img src={example.url} alt="" />
        </button>
      ))}
    </section>
  )
}

export default Examples
