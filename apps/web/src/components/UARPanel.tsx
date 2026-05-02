import { useEffect, useMemo, useState } from 'react'

type RunStatus = 'idle' | 'running' | 'completed' | 'failed'

type ProductTemplate = {
  id: string
  name: string
  description: string
  required_inputs: string[]
  planner: string
  skills: string[]
}

type StructuredResult = {
  title: string
  confidence: string
  confidenceDetail: string
  sections: { label: string; content: string }[]
}

function valueToText(value: unknown) {
  if (value === undefined || value === null) return ''
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

function downloadFile(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

function labelForInput(input: string) {
  if (input === 'input_path') return 'Path'
  if (input === 'question') return 'Question'
  if (input === 'goal') return 'Goal'
  return input
}

function placeholderForInput(input: string) {
  if (input === 'input_path') return './'
  if (input === 'question') return 'e.g., Explain gravity simply'
  if (input === 'goal') return 'What do you want UAR to do?'
  return ''
}

function confidenceLabel(meta: any): { label: string; detail: string } {
  const score = meta?.evaluation?.score
  if (typeof score !== 'number') return { label: 'Not scored yet', detail: 'Run a workflow to generate confidence details.' }
  if (score >= 0.85) return { label: 'High confidence', detail: `Evaluation score: ${score.toFixed(2)}` }
  if (score >= 0.7) return { label: 'Good confidence', detail: `Evaluation score: ${score.toFixed(2)}` }
  if (score >= 0.5) return { label: 'Needs review', detail: `Evaluation score: ${score.toFixed(2)}` }
  return { label: 'Low confidence', detail: `Evaluation score: ${score.toFixed(2)}` }
}

function failureNote(meta: any): string | null {
  const category = meta?.failure?.category
  if (!category || category === 'none') return null
  if (category === 'goal_mismatch') return 'This result may not fully match the request.'
  if (category === 'low_quality_output') return 'This result may be incomplete or thin.'
  if (category === 'timeout') return 'The run timed out. Try smaller input.'
  if (category === 'runtime_error') return 'The workflow hit an execution issue.'
  return `Review recommended: ${category}`
}

function flattenResult(result: any): string {
  if (!result) return ''
  if (typeof result === 'string') return result
  if (Array.isArray(result)) return result.map((item) => valueToText(item)).join('\n\n')
  return valueToText(result)
}

function formatResult(templateId: string | undefined, result: any, meta: any): StructuredResult {
  const confidence = confidenceLabel(meta)
  const text = flattenResult(result)
  const note = failureNote(meta)
  const extraSections = note ? [{ label: '⚠️ Notes', content: note }] : []

  if (!result) {
    return {
      title: 'No result yet',
      confidence: confidence.label,
      confidenceDetail: confidence.detail,
      sections: [{ label: '👋 Start here', content: 'Choose a workflow, provide input, and run it to see structured results here.' }]
    }
  }

  if (templateId === 'repo_analyzer') {
    return {
      title: 'Repository Analysis',
      confidence: confidence.label,
      confidenceDetail: confidence.detail,
      sections: [
        { label: '📁 Structure', content: text },
        { label: '📦 Dependencies', content: 'Dependency details are included in the analysis output when detected.' },
        { label: '🧠 Summary', content: 'Review the structure output and generated summary above.' },
        ...extraSections
      ]
    }
  }

  if (templateId === 'document_summarizer') {
    return {
      title: 'Document Summary',
      confidence: confidence.label,
      confidenceDetail: confidence.detail,
      sections: [
        { label: '📝 Summary', content: text },
        { label: '🔑 Key Points', content: 'Key points are derived from the summary output.' },
        ...extraSections
      ]
    }
  }

  if (templateId === 'smart_qa') {
    return {
      title: 'Answer',
      confidence: confidence.label,
      confidenceDetail: confidence.detail,
      sections: [
        { label: '💬 Answer', content: text },
        ...extraSections
      ]
    }
  }

  return {
    title: 'Workflow Result',
    confidence: confidence.label,
    confidenceDetail: confidence.detail,
    sections: [
      { label: '📌 Result', content: text },
      { label: '🧠 Evaluation', content: valueToText(meta?.evaluation || 'No evaluation available.') },
      ...extraSections
    ]
  }
}

export function UARPanel() {
  const [templates, setTemplates] = useState<ProductTemplate[]>([])
  const [selectedTemplateId, setSelectedTemplateId] = useState('')
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [status, setStatus] = useState<RunStatus>('idle')
  const [message, setMessage] = useState('Choose a task and run it.')
  const [result, setResult] = useState<any>(null)
  const [meta, setMeta] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)

  useEffect(() => {
    async function loadTemplates() {
      try {
        const res = await fetch('/api/v1/product/templates')
        if (!res.ok) throw new Error(`Failed to load templates: HTTP ${res.status}`)
        const data = await res.json()
        setTemplates(data)
        if (data.length) {
          setSelectedTemplateId(data[0].id)
          const defaults: Record<string, string> = {}
          for (const input of data[0].required_inputs || []) {
            defaults[input] = input === 'input_path' ? './' : ''
          }
          setInputs(defaults)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load product templates')
      }
    }
    loadTemplates()
  }, [])

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.id === selectedTemplateId),
    [templates, selectedTemplateId]
  )

  const structuredResult = useMemo(
    () => formatResult(selectedTemplate?.id, result, meta),
    [meta, result, selectedTemplate?.id]
  )

  const selectTemplate = (template: ProductTemplate) => {
    setSelectedTemplateId(template.id)
    const nextInputs: Record<string, string> = {}
    for (const input of template.required_inputs || []) {
      nextInputs[input] = input === 'input_path' ? './' : ''
    }
    setInputs(nextInputs)
    setResult(null)
    setMeta(null)
    setError(null)
    setStatus('idle')
    setMessage('Ready to run.')
  }

  const runProductTemplate = async () => {
    if (!selectedTemplate) return
    setStatus('running')
    setResult(null)
    setMeta(null)
    setError(null)
    setMessage('Running your workflow...')

    try {
      const res = await fetch('/api/v1/product/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id: selectedTemplate.id, inputs })
      })

      if (!res.ok) throw new Error(`Request failed with HTTP ${res.status}`)
      const data = await res.json()

      if (data.status === 'error') {
        setStatus('failed')
        setMessage('Please fix the input and try again.')
        setError((data.errors || []).join('\n'))
        return
      }

      setStatus(data.status === 'completed' ? 'completed' : 'failed')
      setMessage(data.message || 'Workflow finished.')
      setResult(data.result)
      setMeta(data.meta)
    } catch (err) {
      setStatus('failed')
      setMessage('The workflow could not be completed.')
      setError(err instanceof Error ? err.message : 'Unknown error')
    }
  }

  const exportMarkdown = useMemo(() => {
    const lines = [
      `# ${structuredResult.title}`,
      '',
      `## Workflow`,
      selectedTemplate?.name || 'Unknown',
      '',
      `## Status`,
      status,
      '',
      `## Message`,
      message,
      '',
      `## Confidence`,
      `${structuredResult.confidence} — ${structuredResult.confidenceDetail}`,
      '',
      `## Inputs`,
      '```json',
      JSON.stringify(inputs, null, 2),
      '```',
      ''
    ]
    for (const section of structuredResult.sections) {
      lines.push(`## ${section.label}`, section.content, '')
    }
    return `${lines.join('\n')}\n`
  }, [inputs, message, selectedTemplate?.name, status, structuredResult])

  const actionLabel = selectedTemplate?.id === 'smart_qa'
    ? 'Get Answer'
    : selectedTemplate?.id === 'document_summarizer'
      ? 'Summarize'
      : selectedTemplate?.id === 'repo_analyzer'
        ? 'Run Analysis'
        : 'Run Workflow'

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 1100, margin: '0 auto', padding: 20 }}>
      <header style={{ marginBottom: 20 }}>
        <h2 style={{ marginBottom: 4 }}>UAR Tasks</h2>
        <p style={{ marginTop: 0, color: '#555' }}>Pick what you want to do. UAR handles the runtime underneath.</p>
      </header>

      <section style={{ border: '1px solid #ddd', borderRadius: 12, padding: 16, marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>1. Choose task</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
          {templates.map((template) => (
            <button
              key={template.id}
              onClick={() => selectTemplate(template)}
              style={{
                textAlign: 'left',
                padding: 12,
                borderRadius: 10,
                border: selectedTemplateId === template.id ? '2px solid #333' : '1px solid #ccc',
                background: selectedTemplateId === template.id ? '#f7f7f7' : 'white'
              }}
            >
              <strong>{template.name}</strong>
              <div style={{ color: '#666', marginTop: 6, fontSize: 13 }}>{template.description}</div>
              <div style={{ color: '#777', marginTop: 8, fontSize: 12 }}>
                Planner: {template.planner} · Skills: {template.skills?.length ? template.skills.join(' → ') : 'adaptive'}
              </div>
            </button>
          ))}
        </div>
      </section>

      {selectedTemplate && (
        <section style={{ border: '1px solid #ddd', borderRadius: 12, padding: 16, marginBottom: 20 }}>
          <h3 style={{ marginTop: 0 }}>2. Provide input</h3>
          <div style={{ display: 'grid', gap: 12 }}>
            {selectedTemplate.required_inputs.map((input) => (
              <label key={input}>
                <strong>{labelForInput(input)}</strong>
                <textarea
                  value={inputs[input] || ''}
                  onChange={(e) => setInputs((prev) => ({ ...prev, [input]: e.target.value }))}
                  placeholder={placeholderForInput(input)}
                  rows={input === 'input_path' ? 1 : 4}
                  style={{ width: '100%', marginTop: 6 }}
                />
              </label>
            ))}
          </div>
        </section>
      )}

      <section style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 20 }}>
        <button onClick={runProductTemplate} disabled={!selectedTemplate || status === 'running'} style={{ padding: '10px 16px' }}>
          {status === 'running' ? 'Running...' : actionLabel}
        </button>
        <span>Status: <strong>{status}</strong></span>
        {status === 'running' && <span>⚙️ Running your workflow...</span>}
      </section>

      {error && (
        <section style={{ border: '1px solid #d66', background: '#fff4f4', borderRadius: 12, padding: 16, marginBottom: 20 }}>
          <h3 style={{ marginTop: 0 }}>Needs attention</h3>
          <pre style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{error}</pre>
        </section>
      )}

      <section style={{ border: '1px solid #ddd', borderRadius: 12, padding: 16, marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>{structuredResult.title}</h3>
        <p style={{ color: status === 'failed' ? '#9a2222' : '#333' }}>{message}</p>
        <div style={{ border: '1px solid #eee', borderRadius: 10, padding: 10, marginBottom: 14 }}>
          <strong>{structuredResult.confidence}</strong>
          <div style={{ color: '#666', marginTop: 4 }}>{structuredResult.confidenceDetail}</div>
        </div>
        <div style={{ display: 'grid', gap: 12 }}>
          {structuredResult.sections.map((section) => (
            <div key={section.label} style={{ borderTop: '1px solid #eee', paddingTop: 10 }}>
              <h4 style={{ margin: '0 0 6px' }}>{section.label}</h4>
              <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{section.content}</pre>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          <button onClick={() => navigator.clipboard.writeText(exportMarkdown)} disabled={!result}>Copy Markdown</button>
          <button onClick={() => downloadFile('uar-product-run.md', exportMarkdown, 'text/markdown')} disabled={!result}>Download Markdown</button>
          <button onClick={() => downloadFile('uar-product-run.json', JSON.stringify({ template: selectedTemplate, inputs, status, message, structuredResult, result, meta }, null, 2), 'application/json')} disabled={!result}>Download JSON</button>
        </div>
      </section>

      <section style={{ border: '1px solid #ddd', borderRadius: 12, padding: 16 }}>
        <button onClick={() => setShowAdvanced((value) => !value)}>
          {showAdvanced ? 'Hide Details' : 'View Details'}
        </button>
        {showAdvanced && (
          <div style={{ marginTop: 12 }}>
            <h3>Runtime Details</h3>
            <p style={{ color: '#666' }}>Developer-facing metadata for evaluation, failure taxonomy, and runtime inspection.</p>
            <pre style={{ whiteSpace: 'pre-wrap' }}>{valueToText(meta || {})}</pre>
            <h3>Raw Result</h3>
            <pre style={{ whiteSpace: 'pre-wrap' }}>{valueToText(result || {})}</pre>
          </div>
        )}
      </section>
    </div>
  )
}
