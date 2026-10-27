import type { AgentEvent, AgentName } from './api'

export type AgentState = {
  status: 'idle' | AgentEvent['status']
  message: string
}

export type AgentStates = Record<AgentName, AgentState>

export const AGENTS: { name: AgentName; label: string }[] = [
  { name: 'art-director', label: 'Art Director' },
  { name: 'cutter', label: 'Cutter' },
  { name: 'illustrator', label: 'Illustrator' },
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
