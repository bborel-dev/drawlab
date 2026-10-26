export async function traceImage(image: File): Promise<string> {
  const body = new FormData()
  body.append('image', image)
  const response = await fetch('/api/trace', { method: 'POST', body })
  if (!response.ok) {
    throw new Error(`Tracing failed (${response.status})`)
  }
  return response.text()
}
