import type { AgentEvent, AgentName } from './api'

export type AgentState = {
  status: 'idle' | AgentEvent['status']
  message: string
}

export type AgentStates = Record<AgentName, AgentState>

export const AGENTS: { name: AgentName; label: string; model: string }[] = [
  { name: 'art-director', label: 'Analysis', model: 'Muse Spark' },
  { name: 'cutter', label: 'Segmentation', model: 'SAM 3.1' },
  { name: 'illustrator', label: 'Tracing', model: 'vtracer' },
]

export function agentLabel(name: AgentName): string {
  return AGENTS.find((agent) => agent.name === name)?.label ?? name
}

export function initialAgentStates(): AgentStates {
  return Object.fromEntries(AGENTS.map((agent) => [agent.name, { status: 'idle', message: '' }])) as AgentStates
}

export function applyAgentEvent(states: AgentStates, event: AgentEvent): AgentStates {
  return { ...states, [event.agent]: { status: event.status, message: event.message } }
}

export function workingAgent(states: AgentStates): AgentName | null {
  return AGENTS.find((agent) => states[agent.name].status === 'working')?.name ?? null
}
