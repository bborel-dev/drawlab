import { useEffect, useRef, useState, type FormEvent, type MouseEvent } from 'react'
import { SendIcon, StopIcon } from './icons'
import { expectedDuration, formatDuration, recordDuration, type TalkStage } from './talkTiming'

export type TalkAnswer = {
  reply: string
  changed: string[]
}

export type TalkProgress = {
  stage: TalkStage
  message: string
}

type TalkBarProps = {
  onAsk: (prompt: string, onProgress: (progress: TalkProgress) => void) => Promise<TalkAnswer>
  onCancel: () => void
}

type TalkRun = {
  startedAt: number
  stage: TalkStage
  stageStartedAt: number
  expectedEndAt: number
}

const MAX_PROMPT_LENGTH = 500
const PLACEHOLDER = 'Ask Muse Spark: “make the roof red”, “hide the clouds”, “move the sun left”'
const PENDING_PLACEHOLDER = 'Muse Spark is reading your request…'
const FAILURE_REPLY = 'Could not reach the studio, please try again.'
const CANCELLED_REPLY = 'Request cancelled.'
const TICK_MS = 1000

function TalkBar({ onAsk, onCancel }: TalkBarProps) {
  const [prompt, setPrompt] = useState('')
  const [run, setRun] = useState<TalkRun | null>(null)
  const runRef = useRef<TalkRun | null>(null)
  const [answer, setAnswer] = useState<TalkAnswer | null>(null)
  const [progress, setProgress] = useState(PENDING_PLACEHOLDER)
  const pending = run !== null

  function changeRun(next: TalkRun | null) {
    runRef.current = next
    setRun(next)
  }

  function report({ stage, message }: TalkProgress) {
    setProgress(message)
    const current = runRef.current
    if (!current || current.stage === stage) return
    const now = Date.now()
    recordDuration(current.stage, now - current.stageStartedAt)
    changeRun({ ...current, stage, stageStartedAt: now, expectedEndAt: now + expectedDuration(stage) })
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const request = prompt.trim()
    if (!request || runRef.current) return
    const startedAt = Date.now()
    const expectedEndAt = startedAt + expectedDuration('planning') + expectedDuration('repainting')
    changeRun({ startedAt, stage: 'planning', stageStartedAt: startedAt, expectedEndAt })
    setProgress(PENDING_PLACEHOLDER)
    try {
      setAnswer(await onAsk(request, report))
      finishStage()
      setPrompt('')
    } catch (error) {
      setAnswer({ reply: isAbort(error) ? CANCELLED_REPLY : FAILURE_REPLY, changed: [] })
    } finally {
      changeRun(null)
    }
  }

  function cancel(event: MouseEvent<HTMLButtonElement>) {
    event.preventDefault()
    onCancel()
  }

  function finishStage() {
    const current = runRef.current
    if (current) recordDuration(current.stage, Date.now() - current.stageStartedAt)
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
      <form className={pending ? 'talk-bar talk-bar-pending' : 'talk-bar'} onSubmit={submit} aria-busy={pending}>
        <span className="talk-bubble" aria-hidden="true">
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
        {run && <TalkTimer run={run} />}
        {pending ? (
          <button
            key="cancel"
            type="button"
            className="talk-send"
            onClick={cancel}
            aria-label="Cancel the request"
            title="Cancel"
          >
            <StopIcon />
          </button>
        ) : (
          <button key="send" type="submit" className="talk-send" disabled={!prompt.trim()} aria-label="Send">
            <SendIcon />
          </button>
        )}
      </form>
    </div>
  )
}

function TalkTimer({ run }: { run: TalkRun }) {
  const now = useNow()
  const overdue = now >= run.expectedEndAt
  return (
    <span className="talk-timer" role="timer">
      {formatDuration(now - run.startedAt)}
      <span className="talk-timer-estimate">
        {overdue ? 'almost done' : `/ ~${formatDuration(run.expectedEndAt - run.startedAt)}`}
      </span>
    </span>
  )
}

function useNow(): number {
  const [now, setNow] = useState(Date.now)
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), TICK_MS)
    return () => clearInterval(timer)
  }, [])
  return now
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export default TalkBar
