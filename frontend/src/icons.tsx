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

export function BackIcon() {
  return (
    <Icon>
      <path d="M13 8 H3" />
      <path d="M7 4 L3 8 L7 12" />
    </Icon>
  )
}

export function SparkleIcon() {
  return (
    <Icon>
      <path d="M8 1.5 C8.5 5 11 7.5 14.5 8 C11 8.5 8.5 11 8 14.5 C7.5 11 5 8.5 1.5 8 C5 7.5 7.5 5 8 1.5 Z" />
    </Icon>
  )
}
