import type { ReactNode } from 'react'

type IconProps = {
  children: ReactNode
}

function Icon({ children }: IconProps) {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  )
}

export function EyeIcon({ open }: { open: boolean }) {
  return (
    <Icon>
      <path d="M1.5 8 C3.5 4.6 5.6 3 8 3 C10.4 3 12.5 4.6 14.5 8 C12.5 11.4 10.4 13 8 13 C5.6 13 3.5 11.4 1.5 8 Z" />
      <circle cx="8" cy="8" r="2.2" />
      {!open && <path d="M2.5 13.5 L13.5 2.5" />}
    </Icon>
  )
}

export function ChevronIcon() {
  return (
    <Icon>
      <path d="M6 4 L10 8 L6 12" />
    </Icon>
  )
}

export function UndoIcon() {
  return (
    <Icon>
      <path d="M5.5 3.5 L2.5 6.5 L5.5 9.5" />
      <path d="M2.5 6.5 H10 C12 6.5 13.5 8 13.5 10 C13.5 12 12 13.5 10 13.5 H7" />
    </Icon>
  )
}

export function RedoIcon() {
  return (
    <Icon>
      <path d="M10.5 3.5 L13.5 6.5 L10.5 9.5" />
      <path d="M13.5 6.5 H6 C4 6.5 2.5 8 2.5 10 C2.5 12 4 13.5 6 13.5 H9" />
    </Icon>
  )
}

export function SendIcon() {
  return (
    <Icon>
      <path d="M8 13 V3" />
      <path d="M4 7 L8 3 L12 7" />
    </Icon>
  )
}

export function StopIcon() {
  return (
    <Icon>
      <rect x="4.5" y="4.5" width="7" height="7" rx="1.5" fill="currentColor" />
    </Icon>
  )
}

export function GitHubIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
    </svg>
  )
}

export function BackIcon() {
  return (
    <Icon>
      <path d="M13 8 H3" />
      <path d="M7 4 L3 8 L7 12" />
    </Icon>
  )
}
