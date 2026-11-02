import { useState, type FormEvent } from 'react'
import { SparkleIcon } from './icons'

export type TalkAnswer = {
  reply: string
  changed: string[]
}

type TalkBarProps = {
  onAsk: (prompt: string, onProgress: (message: string) => void) => Promise<TalkAnswer>
}

const MAX_PROMPT_LENGTH = 500
const PLACEHOLDER = 'Talk to the drawing: “make the roof red”, “hide the clouds”, “move the sun left”'
const PENDING_PLACEHOLDER = 'Muse Spark is reading your request…'
const FAILURE_REPLY = 'Could not reach the studio, please try again.'

function TalkBar({ onAsk }: TalkBarProps) {
  const [prompt, setPrompt] = useState('')
  const [pending, setPending] = useState(false)
  const [answer, setAnswer] = useState<TalkAnswer | null>(null)
  const [progress, setProgress] = useState(PENDING_PLACEHOLDER)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const request = prompt.trim()
    if (!request || pending) return
    setPending(true)
    setProgress(PENDING_PLACEHOLDER)
    try {
      setAnswer(await onAsk(request, setProgress))
      setPrompt('')
    } catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) setAnswer({ reply: FAILURE_REPLY, changed: [] })
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="talk">
      {answer && (
        <p className="talk-reply" role="status">
          {answer.reply}
          {answer.changed.length > 0 && (
            <span className="talk-changed"> · Changed: {answer.changed.join(', ')}</span>
          )}
        </p>
      )}
      <form className={pending ? 'talk-bar talk-bar-pending' : 'talk-bar'} onSubmit={submit}>
        <span className="talk-badge" aria-hidden="true">
          <SparkleIcon />
          AI
        </span>
        <input
          className="talk-input"
          type="text"
          value={pending ? '' : prompt}
          disabled={pending}
          maxLength={MAX_PROMPT_LENGTH}
          placeholder={pending ? progress : PLACEHOLDER}
          aria-label="Talk to the drawing"
          onChange={(event) => setPrompt(event.target.value)}
        />
      </form>
    </div>
  )
}

export default TalkBar
