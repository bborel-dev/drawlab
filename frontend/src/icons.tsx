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

export function ImageIcon() {
  return (
    <Icon>
      <rect x="2" y="3" width="12" height="10" rx="2" />
      <circle cx="10.5" cy="6" r="1.2" />
      <path d="M2.5 11.5 L6 8 L9.5 11.5" />
    </Icon>
  )
}

export function PlanIcon() {
  return (
    <Icon>
      <path d="M3 2.5 H10 L13 5.5 V13.5 H3 Z" />
      <path d="M5.5 7.5 H10.5 M5.5 10 H9" />
    </Icon>
  )
}

export function ScissorsIcon() {
  return (
    <Icon>
      <circle cx="4.5" cy="4.5" r="2" />
      <circle cx="4.5" cy="11.5" r="2" />
      <path d="M6.2 5.6 L13.5 12 M6.2 10.4 L13.5 4" />
    </Icon>
  )
}

export function PenIcon() {
  return (
    <Icon>
      <path d="M10.5 2.5 L13.5 5.5 L6 13 L2.5 13.5 L3 10 Z" />
      <path d="M9 4 L12 7" />
    </Icon>
  )
}

export function LayersIcon() {
  return (
    <Icon>
      <path d="M8 2.5 L14 5.5 L8 8.5 L2 5.5 Z" />
      <path d="M2 8.5 L8 11.5 L14 8.5" />
      <path d="M2 11 L8 14 L14 11" />
    </Icon>
  )
}
