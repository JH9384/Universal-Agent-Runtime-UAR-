export function downloadMarkdown(filename: string, markdown: string): void {
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export function evidencePackFilename(generatedAt: number): string {
  const stamp = new Date(generatedAt).toISOString().replace(/[:.]/g, '-')
  return `uar-evidence-pack-${stamp}.md`
}
