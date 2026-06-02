import { useState, useCallback } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import { authHeaders } from '../utils/auth'
import styles from './IncidentWorkbench.module.css'

interface Incident {
  id: string
  title: string
  description: string
  status: 'open' | 'investigating' | 'resolved' | 'closed'
  severity: 'low' | 'medium' | 'high' | 'critical'
  linked_run_ids: string[]
  linked_rec_ids: string[]
  resolution_notes: string
  created_at: number
  updated_at: number
}

export function IncidentWorkbench({
  onOpenReplay,
}: {
  onOpenReplay?: (runId: string) => void
}) {
  const { data, loading, error, refetch } = useApiFetch<Incident[]>(
    '/api/uar/incidents',
    { interval: 30_000 }
  )
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Incident | null>(null)
  const [statusError, setStatusError] = useState<string | null>(null)

  const incidents = data ?? []
  const openCount = incidents.filter((i) => i.status !== 'resolved' && i.status !== 'closed').length

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <div>
          <h4 className={styles.panelTitle}>Incident Workbench</h4>
          <span className={styles.meta}>{openCount} open</span>
        </div>
        <button className={styles.createBtn} onClick={() => { setFormOpen(true); setEditing(null) }}>
          + New Incident
        </button>
      </div>

      {formOpen && (
        <IncidentForm
          incident={editing}
          onSaved={() => { setFormOpen(false); refetch() }}
          onCancel={() => setFormOpen(false)}
        />
      )}

      {loading && <div className={styles.loading}>Loading incidents…</div>}
      {error && <div className={styles.error}>{error}</div>}
      {statusError && <div className={styles.error}>{statusError}</div>}
      {incidents.length === 0 && !loading && !error && (
        <div className={styles.emptyState}>No incidents yet. Create one to start tracking.</div>
      )}

      <div className={styles.incidentList}>
        {incidents.map((inc) => (
          <IncidentCard
            key={inc.id}
            incident={inc}
            onEdit={() => { setEditing(inc); setFormOpen(true) }}
            onStatusChange={async (status) => {
              setStatusError(null)
              try {
                const res = await fetch(`/api/uar/incidents/${inc.id}`, {
                  method: 'PUT',
                  headers: { 'Content-Type': 'application/json', ...authHeaders() },
                  body: JSON.stringify({ status }),
                })
                if (!res.ok) throw new Error(`Status update failed: ${res.status}`)
                refetch()
              } catch (e) {
                setStatusError(e instanceof Error ? e.message : 'Status update failed')
              }
            }}
            onOpenReplay={onOpenReplay}
          />
        ))}
      </div>
    </div>
  )
}

function IncidentCard({
  incident,
  onEdit,
  onStatusChange,
  onOpenReplay,
}: {
  incident: Incident
  onEdit: () => void
  onStatusChange: (s: string) => void
  onOpenReplay?: (runId: string) => void
}) {
  const severityClass = {
    low: styles.sevLow,
    medium: styles.sevMedium,
    high: styles.sevHigh,
    critical: styles.sevCritical,
  }[incident.severity] || ''

  const statusClass = {
    open: styles.statusOpen,
    investigating: styles.statusInvestigating,
    resolved: styles.statusResolved,
    closed: styles.statusClosed,
  }[incident.status] || ''

  return (
    <div className={`${styles.card} ${severityClass}`}>
      <div className={styles.cardHeader}>
        <span className={styles.cardId}>{incident.id}</span>
        <span className={`${styles.statusBadge} ${statusClass}`}>{incident.status}</span>
        <span className={`${styles.sevBadge} ${severityClass}`}>{incident.severity}</span>
        <button className={styles.editBtn} onClick={onEdit}>Edit</button>
      </div>
      <h5 className={styles.cardTitle}>{incident.title}</h5>
      <p className={styles.cardDesc}>{incident.description}</p>

      {incident.linked_run_ids.length > 0 && (
        <div className={styles.linkSection}>
          <span className={styles.linkLabel}>Runs:</span>
          {incident.linked_run_ids.map((rid) => (
            <button
              key={rid}
              className={styles.linkTag}
              onClick={() => onOpenReplay?.(rid)}
            >
              {rid}
            </button>
          ))}
        </div>
      )}

      {incident.resolution_notes && (
        <div className={styles.notes}>
          <strong>Resolution:</strong> {incident.resolution_notes}
        </div>
      )}

      <div className={styles.cardActions}>
        {incident.status !== 'resolved' && (
          <button className={styles.actionBtn} onClick={() => onStatusChange('resolved')}>
            Mark Resolved
          </button>
        )}
        {incident.status === 'resolved' && (
          <button className={styles.actionBtn} onClick={() => onStatusChange('investigating')}>
            Reopen
          </button>
        )}
      </div>
    </div>
  )
}

function IncidentForm({
  incident,
  onSaved,
  onCancel,
}: {
  incident: Incident | null
  onSaved: () => void
  onCancel: () => void
}) {
  const [title, setTitle] = useState(incident?.title ?? '')
  const [description, setDescription] = useState(incident?.description ?? '')
  const [severity, setSeverity] = useState(incident?.severity ?? 'medium')
  const [status, setStatus] = useState(incident?.status ?? 'open')
  const [linkedRuns, setLinkedRuns] = useState(incident?.linked_run_ids?.join(',') ?? '')
  const [linkedRecs, setLinkedRecs] = useState(incident?.linked_rec_ids?.join(',') ?? '')
  const [resolutionNotes, setResolutionNotes] = useState(incident?.resolution_notes ?? '')
  const [validationError, setValidationError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const handleSubmit = useCallback(async () => {
    if (!title.trim()) { setValidationError('Title is required'); return }
    setValidationError(null)
    setSaveError(null)
    setSaving(true)
    const body = {
      title,
      description,
      severity,
      status,
      linked_run_ids: linkedRuns.split(',').map((s) => s.trim()).filter(Boolean),
      linked_rec_ids: linkedRecs.split(',').map((s) => s.trim()).filter(Boolean),
      resolution_notes: resolutionNotes,
    }
    const url = incident ? `/api/uar/incidents/${incident.id}` : '/api/uar/incidents'
    const method = incident ? 'PUT' : 'POST'
    try {
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error(`Save failed: ${res.status}`)
      onSaved()
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Save failed')
    } finally {
      setSaving(false)
    }
  }, [title, description, severity, status, linkedRuns, linkedRecs, resolutionNotes, incident, onSaved])

  return (
    <div className={styles.formOverlay}>
      <div className={styles.form}>
        <h5>{incident ? 'Edit Incident' : 'New Incident'}</h5>
        {validationError && <div className={styles.formError}>{validationError}</div>}
        {saveError && <div className={styles.formError}>{saveError}</div>}
        <input className={styles.input} placeholder="Title *" value={title} onChange={(e) => { setTitle(e.target.value); if (e.target.value.trim()) setValidationError(null) }} />
        <textarea className={styles.textarea} placeholder="Description" value={description} onChange={(e) => setDescription(e.target.value)} />
        <div className={styles.formRow}>
          <select className={styles.select} aria-label="Severity" value={severity} onChange={(e) => setSeverity(e.target.value as Incident['severity'])}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
          <select className={styles.select} aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value as Incident['status'])}>
            <option value="open">Open</option>
            <option value="investigating">Investigating</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>
        </div>
        <input className={styles.input} placeholder="Linked run IDs (comma-separated)" value={linkedRuns} onChange={(e) => setLinkedRuns(e.target.value)} />
        <input className={styles.input} placeholder="Linked recommendation IDs (comma-separated)" value={linkedRecs} onChange={(e) => setLinkedRecs(e.target.value)} />
        <textarea className={styles.textarea} placeholder="Resolution notes" value={resolutionNotes} onChange={(e) => setResolutionNotes(e.target.value)} />
        <div className={styles.formActions}>
          <button className={styles.saveBtn} onClick={handleSubmit} disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
          <button className={styles.cancelBtn} onClick={onCancel}>Cancel</button>
        </div>
      </div>
    </div>
  )
}

