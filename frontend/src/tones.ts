export type Tone = {
  color: string
  share: number
}

export type ToneFamily = {
  color: string
  members: string[]
  count: number
}

const FILL_PATTERN = /fill="(#[0-9a-fA-F]{6})"/g
const PAINT_PATTERN = /(fill|stroke)="(#[0-9a-fA-F]{6})"/g
const SAME_FAMILY_DISTANCE = 30
const MAX_FAMILIES = 12

export function toneFamilies(markups: string[]): ToneFamily[] {
  const families: ToneFamily[] = []
  for (const [color, count] of fillCounts(markups)) {
    const nearest = nearestFamily(families, color)
    const joins = nearest && (families.length >= MAX_FAMILIES || colorDistance(nearest.color, color) < SAME_FAMILY_DISTANCE)
    if (nearest && joins) {
      nearest.members.push(color)
      nearest.count += count
    } else {
      families.push({ color, members: [color], count })
    }
  }
  return families.sort((a, b) => b.count - a.count)
}

export function familyTones(families: ToneFamily[]): Tone[] {
  const total = families.reduce((sum, family) => sum + family.count, 0)
  return families.map((family) => ({ color: family.color, share: total ? family.count / total : 0 }))
}

export function shiftedFamily(family: ToneFamily, target: string): Map<string, string> {
  const goal = toRgb(target)
  const base = toRgb(family.color)
  return new Map(
    family.members.map((member) => {
      const rgb = toRgb(member)
      return [member, toHex(rgb.map((channel, index) => channel - base[index] + goal[index]))]
    }),
  )
}

export function replaceColors(markup: string, colors: Map<string, string>): string {
  return markup.replace(PAINT_PATTERN, (match, attribute: string, color: string) => {
    const next = colors.get(color.toUpperCase())
    return next ? `${attribute}="${next}"` : match
  })
}

export function fillsByFrequency(markup: string): string[] {
  return fillCounts([markup]).map(([color]) => color.toLowerCase())
}

function fillCounts(markups: string[]): [string, number][] {
  const counts = new Map<string, number>()
  markups.forEach((markup) => {
    for (const [, color] of markup.matchAll(FILL_PATTERN)) {
      const key = color.toUpperCase()
      counts.set(key, (counts.get(key) ?? 0) + 1)
    }
  })
  return [...counts.entries()].sort((a, b) => b[1] - a[1])
}

function nearestFamily(families: ToneFamily[], color: string): ToneFamily | undefined {
  let best: ToneFamily | undefined
  let bestDistance = Infinity
  families.forEach((family) => {
    const distance = colorDistance(family.color, color)
    if (distance < bestDistance) {
      best = family
      bestDistance = distance
    }
  })
  return best
}

function colorDistance(first: string, second: string): number {
  const [r1, g1, b1] = toRgb(first)
  const [r2, g2, b2] = toRgb(second)
  return Math.hypot(r1 - r2, g1 - g2, b1 - b2)
}

function toHex(rgb: number[]): string {
  const channels = rgb.map((channel) => Math.min(255, Math.max(0, Math.round(channel))))
  return `#${channels.map((channel) => channel.toString(16).padStart(2, '0').toUpperCase()).join('')}`
}

function toRgb(hex: string): [number, number, number] {
  const value = Number.parseInt(hex.slice(1), 16)
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255]
}
