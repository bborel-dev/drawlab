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
