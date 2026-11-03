import { useEffect, useState, type FormEvent } from 'react'
import { createPortal } from 'react-dom'
import CompareFrame from './CompareFrame'
import { useEscape } from './useEscape'
import ViewSwitch, { type CompareView } from './ViewSwitch'

export type Proposal = {
  image: string
  reply: string
  busy: boolean
}

export type ProposalChoice = { kind: 'accept' } | { kind: 'retouch'; instruction: string } | { kind: 'discard' }

type RepaintProposalProps = {
  proposal: Proposal
  currentSvg: string
  onChoose: (choice: ProposalChoice) => void
}

const MAX_INSTRUCTION_LENGTH = 500

function RepaintProposal({ proposal, currentSvg, onChoose }: RepaintProposalProps) {
  const [view, setView] = useState<CompareView>('compare')
  const [instruction, setInstruction] = useState('')
  const beforeUrl = useSvgUrl(currentSvg)
  useEscape(() => !proposal.busy && onChoose({ kind: 'discard' }))

  function retouch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = instruction.trim()
    if (!text || proposal.busy) return
    setInstruction('')
    onChoose({ kind: 'retouch', instruction: text })
  }

  return createPortal(
    <div className="dialog-backdrop">
      <section className="proposal glass" role="dialog" aria-modal="true" aria-labelledby="proposal-title">
        <header className="proposal-header">
          <div>
            <h2 id="proposal-title" className="proposal-title">
              Here is the new scene
            </h2>
            <p className="proposal-reply">{proposal.reply}</p>
          </div>
          <ViewSwitch view={view} onChange={setView} />
        </header>
        <div className="proposal-frame" aria-busy={proposal.busy}>
          {beforeUrl && (
            <CompareFrame sourceUrl={beforeUrl} sourceFormat="SVG" resultFormat="Muse Image" view={view}>
              <img className="proposal-image" src={proposal.image} alt="Scene proposed by Muse Image" />
            </CompareFrame>
          )}
          {proposal.busy && <p className="proposal-busy">Muse Image is retouching the scene…</p>}
        </div>
        <form className="proposal-retouch" onSubmit={retouch}>
          <input
            className="proposal-input"
            type="text"
            value={instruction}
            disabled={proposal.busy}
            maxLength={MAX_INSTRUCTION_LENGTH}
            placeholder="Not quite? Retouch it: “make the colors warmer”"
            aria-label="Retouch the proposal"
            onChange={(event) => setInstruction(event.target.value)}
          />
          <button type="submit" className="button button-secondary" disabled={proposal.busy || !instruction.trim()}>
            Retouch
          </button>
        </form>
        <footer className="proposal-actions">
          <button
            type="button"
            className="button button-ghost"
            disabled={proposal.busy}
            onClick={() => onChoose({ kind: 'discard' })}
          >
            Discard
          </button>
          <button
            type="button"
            className="button button-primary"
            disabled={proposal.busy}
            onClick={() => onChoose({ kind: 'accept' })}
          >
            Draw it
          </button>
        </footer>
      </section>
    </div>,
    document.body,
  )
}

function useSvgUrl(svg: string): string | null {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    const objectUrl = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }))
    setUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [svg])
  return url
}

export default RepaintProposal
