export type CompareView = 'before' | 'compare' | 'after'

const VIEWS: { value: CompareView; label: string }[] = [
  { value: 'before', label: 'Before' },
  { value: 'compare', label: 'Compare' },
  { value: 'after', label: 'After' },
]

type ViewSwitchProps = {
  view: CompareView
  onChange: (view: CompareView) => void
}

function ViewSwitch({ view, onChange }: ViewSwitchProps) {
  return (
    <div className="view-switch" role="group" aria-label="View">
      {VIEWS.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={view === option.value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export default ViewSwitch
