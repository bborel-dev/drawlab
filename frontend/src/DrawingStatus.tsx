export type StepState = 'done' | 'active' | 'pending'

export type Step = {
  label: string
  state: StepState
}

type DrawingStatusProps = {
  agent: string
  action: string
  detail: string
  progress: number
  steps: Step[]
}

function DrawingStatus({ agent, action, detail, progress, steps }: DrawingStatusProps) {
  return (
    <section className="drawing-status" aria-label="Progress">
      <div className="status-line">
        <p aria-live="polite">
          <strong>{agent}</strong> <span>· {action}</span>
        </p>
        <span className="status-detail">{detail}</span>
      </div>
      <div
        className="progress"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(progress * 100)}
      >
        <div className="progress-fill" style={{ width: `${Math.round(progress * 100)}%` }} />
      </div>
      <ol className="steps" aria-label="Agents">
        {steps.map((step) => (
          <li key={step.label} className={`step step-${step.state}`}>
            <span className="step-dot" aria-hidden="true">
              {step.state === 'done' && (
                <svg width="10" height="10" viewBox="0 0 10 10">
                  <path
                    d="M2 5.2 L4.2 7.4 L8 3"
                    fill="none"
                    stroke="#FFFFFF"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
            </span>
            {step.label}
          </li>
        ))}
      </ol>
    </section>
  )
}

export default DrawingStatus
