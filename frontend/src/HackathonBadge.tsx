const MODELS = ['Muse Spark', 'SAM 3.1']

function HackathonBadge() {
  return (
    <div className="hackathon">
      <p className="hackathon-badge">
        <span className="hackathon-label">Built for the</span>
        <span>Meta Global AI Developer Hackathon 2026</span>
      </p>
      <p className="powered-by">
        Powered by{' '}
        {MODELS.map((model, index) => (
          <span key={model}>
            {index > 0 && (
              <span className="powered-separator" aria-hidden="true">
                ·
              </span>
            )}
            <span className="model-name">{model}</span>
          </span>
        ))}
      </p>
    </div>
  )
}

export default HackathonBadge
