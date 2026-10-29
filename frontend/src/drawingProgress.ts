import { agentLabel, AGENTS, workingAgent, type AgentState, type AgentStates } from './agents'
import type { Step, StepState } from './DrawingStatus'

export type DrawingProgress = {
  agent: string
  action: string
  detail: string
  progress: number
  steps: Step[]
}

type ProgressInput = {
  states: AgentStates
  currentLayer: string | null
  startedLayers: number
  totalLayers: number
  streamDone: boolean
  revealingMasks: boolean
}

const PLANNING_SHARE = 0.1
const CUTTING_SHARE = 0.2
const DRAWING_SHARE = 1 - PLANNING_SHARE - CUTTING_SHARE

export function drawingProgress(input: ProgressInput): DrawingProgress {
  return {
    ...currentAction(input),
    detail: layerDetail(input),
    progress: overallProgress(input),
    steps: AGENTS.map((agent) => ({ label: agent.label, model: agent.model, state: stepState(agent.name, input) })),
  }
}

function currentAction({ states, currentLayer, revealingMasks }: ProgressInput): { agent: string; action: string } {
  if (revealingMasks) return { agent: agentLabel('cutter'), action: lowerFirst(states.cutter.message) }
  if (currentLayer) return { agent: agentLabel('illustrator'), action: `drawing ${currentLayer}` }
  const agent = workingAgent(states)
  if (agent) return { agent: agentLabel(agent), action: lowerFirst(states[agent].message) }
  return { agent: agentLabel('art-director'), action: 'getting ready' }
}

function layerDetail({ startedLayers, totalLayers, streamDone }: ProgressInput): string {
  if (startedLayers === 0) return ''
  return streamDone ? `Layer ${startedLayers} of ${totalLayers}` : `Layer ${startedLayers}`
}

function overallProgress({ states, startedLayers, totalLayers, streamDone }: ProgressInput): number {
  const planned = isDone(states['art-director']) ? PLANNING_SHARE : 0
  const cut = isDone(states.cutter) ? CUTTING_SHARE : 0
  const expectedLayers = streamDone ? totalLayers : totalLayers + 1
  return planned + cut + DRAWING_SHARE * (startedLayers / Math.max(expectedLayers, 1))
}

function stepState(
  name: (typeof AGENTS)[number]['name'],
  { states, startedLayers, revealingMasks }: ProgressInput,
): StepState {
  if (revealingMasks && name !== 'art-director') return name === 'cutter' ? 'active' : 'pending'
  if (name === 'illustrator') return startedLayers > 0 || states.illustrator.status !== 'idle' ? 'active' : 'pending'
  if (isDone(states[name])) return 'done'
  return states[name].status === 'working' ? 'active' : 'pending'
}

function isDone(state: AgentState): boolean {
  return state.status === 'done'
}

function lowerFirst(text: string): string {
  return text.charAt(0).toLowerCase() + text.slice(1)
}
