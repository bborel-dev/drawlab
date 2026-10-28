import type { ReactNode } from 'react'
import { ImageIcon, LayersIcon, PenIcon, PlanIcon, ScissorsIcon } from './icons'

type Step = {
  icon: ReactNode
  title: string
  tool?: string
}

const STEPS: Step[] = [
  { icon: <ImageIcon />, title: 'Your image' },
  { icon: <PlanIcon />, title: 'Art Director', tool: 'Muse Spark' },
  { icon: <ScissorsIcon />, title: 'Cutter', tool: 'SAM 3.1' },
  { icon: <PenIcon />, title: 'Illustrator', tool: 'Vector tracer' },
  { icon: <LayersIcon />, title: 'Named SVG layers' },
]

function HowItWorks() {
  return (
    <aside className="how-it-works" aria-labelledby="how-it-works-title">
      <h2 id="how-it-works-title" className="how-title">
        How it works
      </h2>
      <ol className="how-steps">
        {STEPS.map((step) => (
          <li key={step.title} className="how-step">
            <span className="how-icon" aria-hidden="true">
              {step.icon}
            </span>
            <span className="how-label">
              <span className="how-step-title">{step.title}</span>
              {step.tool && <span className="how-tool">{step.tool}</span>}
            </span>
          </li>
        ))}
      </ol>
    </aside>
  )
}

export default HowItWorks
