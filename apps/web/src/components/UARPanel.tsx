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
  if (input === 'question') return 'What do you want to know?'
  if (input === 'goal') return 'What do you want UAR to do?'
  return ''
}

export function UARPanel() {
  const [templates, setTemplates] = useState<ProductTemplate[]>([])
  const [selectedTemplateId, setSelectedTemplateId] = useState('')
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [status, setStatus] = useState<RunStatus>('idle')
  const [message, setMessage] = useState('Choose a workflow and run it.')
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
    setMessage('Running workflow...')

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
      '# UAR Product Run',
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
      `## Inputs`,
      '```json',
      JSON.stringify(inputs, null, 2),
      '```',
      '',
      `## Result`,
      '```json',
      JSON.stringify(result || [], null, 2),
      '```'
    ]
    return `${lines.join('\n')}\n`
  }, [inputs, message, result, selectedTemplate?.name, status])

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 1100, margin: '0 auto', padding: 20 }}>
      <header style={{ marginBottom: 20 }}>
        <h2 style={{ marginBottom: 4 }}>UAR Workflows</h2>
        <p style={{ marginTop: 0, color: '#555' }}>Choose a workflow, provide the needed input, and run safely.</p>
      </header>

      <section style={{ border: '1px solid #ddd', borderRadius: 12, padding: 16, marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>1. Choose workflow</h3>
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
          {status === 'running' ? 'Running...' : 'Run Workflow'}
        </button>
        <span>Status: <strong>{status}</strong></span>
      </section>

      {error && (
        <section style={{ border: '1px solid #d66', background: '#fff4f4', borderRadius: 12, padding: 16, marginBottom: 20 }}>
          <h3 style={{ marginTop: 0 }}>Needs attention</h3>
          <pre style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{error}</pre>
        </section>
      )}

      <section style={{ border: '1px solid #ddd', borderRadius: 12, padding: 16, marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>Result</h3>
        <p style={{ color: status === 'failed' ? '#9a2222' : '#333' }}>{message}</p>
        <pre style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{valueToText(result || 'No result yet.')}</pre>
        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          <button onClick={() => navigator.clipboard.writeText(exportMarkdown)} disabled={!result}>Copy Markdown</button>
          <button onClick={() => downloadFile('uar-product-run.md', exportMarkdown, 'text/markdown')} disabled={!result}>Download Markdown</button>
          <button onClick={() => downloadFile('uar-product-run.json', JSON.stringify({ template: selectedTemplate, inputs, status, message, result, meta }, null, 2), 'application/json')} disabled={!result}>Download JSON</button>
        </div>
      </section>

      <section style={{ border: '1px solid #ddd', borderRadius: 12, padding: 16 }}>
        <button onClick={() => setShowAdvanced((value) => !value)}>
          {showAdvanced ? 'Hide Advanced' : 'Show Advanced'}
        </button>
        {showAdvanced && (
          <div style={{ marginTop: 12 }}>
            <h3>Runtime Meta</h3>
            <pre style={{ whiteSpace: 'pre-wrap' }}>{valueToText(meta || {})}</pre>
          </div>
        )}
      </section>
    </div>
  )
}
