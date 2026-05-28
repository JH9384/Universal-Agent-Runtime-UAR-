import { useState } from 'react'
import type { Preset } from './FilePicker'
import styles from './UARPanel.module.css'

interface PresetsPanelProps {
  presets: Preset[]
  presetsLoaded: boolean
  presetsError: boolean
  folderPresets: Preset[]
  isRunning: boolean
  inputPath: string
  onPick: (path: string) => void
  onAddPreset: (name: string, path: string) => void
  onRemovePreset: (path: string) => void
}

function chip(active: boolean, disabled: boolean): string {
  const base = styles.chip
  if (disabled) return `${base} ${styles.chipDisabled}`
  if (active) return `${base} ${styles.chipActive}`
  return base
}

export default function PresetsPanel({
  presets,
  presetsLoaded,
  presetsError,
  folderPresets,
  isRunning,
  inputPath,
  onPick,
  onAddPreset,
  onRemovePreset,
}: PresetsPanelProps) {
  const [showAdd, setShowAdd] = useState(false)
  const [newName, setNewName] = useState('')
  const [newPath, setNewPath] = useState('')

  const allPresets = (() => {
    const serverPaths = new Set(presets.map((p) => p.path))
    return [...presets, ...folderPresets.filter((fp) => !serverPaths.has(fp.path))]
  })()

  const handleAdd = () => {
    const name = newName.trim()
    const path = newPath.trim()
    if (!name || !path) return
    onAddPreset(name, path)
    setNewName('')
    setNewPath('')
    setShowAdd(false)
  }

  return (
    <div className={styles.presetsContainer}>
      <div className={styles.label} title="Quick access to pre-configured project directories">Presets</div>
      {!presetsLoaded && <span className={styles.loadingText}>(loading…)</span>}
      {presetsLoaded && presetsError && <span className={styles.errorText}>Failed to load presets — check server</span>}
      {presetsLoaded && !presetsError && allPresets.length === 0 && <span className={styles.loadingText}>(none)</span>}
      {allPresets.map((p) => {
        const isUser = folderPresets.some((fp) => fp.path === p.path)
        return (
          <span key={p.path} className={styles.presetRow}>
            <button disabled={isRunning} onClick={() => onPick(p.path)} className={chip(inputPath === p.path, isRunning)} title={p.path}>
              {p.name}
            </button>
            {isUser && (
              <button onClick={() => onRemovePreset(p.path)} className={styles.deleteButton} title="Remove preset" aria-label={`Remove preset ${p.name}`}>✕</button>
            )}
          </span>
        )
      })}
      <button onClick={() => setShowAdd((v) => !v)} className={styles.presetButton} title="Add custom folder preset">+</button>
      {showAdd && (
        <div className={styles.addPresetForm}>
          <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Name…" className={`${styles.advancedOverrideInput} ${styles.addPresetInput}`} />
          <input value={newPath} onChange={(e) => setNewPath(e.target.value)} placeholder="/path…" className={`${styles.advancedOverrideInput} ${styles.addPresetInputPath}`} onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleAdd() } }} />
          <button onClick={handleAdd} disabled={!newName.trim() || !newPath.trim()} className={styles.smallButton}>Add</button>
          <button onClick={() => setShowAdd(false)} className={styles.smallButton}>Cancel</button>
        </div>
      )}
    </div>
  )
}
