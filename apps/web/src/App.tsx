import { useState } from 'react'
import { UARPanel } from './components/UARPanel'
import { UARSimplePanel } from './components/UARSimplePanel'
import { Dashboard } from './components/Dashboard'
import styles from './App.module.css'

const MODE_KEY = 'uar.ui.mode'

type AppMode = 'advanced' | 'simple' | 'dashboard'

export default function App() {
  const [mode, setMode] = useState<AppMode>(() => {
    try {
      const saved = localStorage.getItem(MODE_KEY)
      if (saved === 'simple' || saved === 'dashboard') return saved
      return 'advanced'
    } catch {
      return 'advanced'
    }
  })
  const [previousMode, setPreviousMode] = useState<AppMode>('advanced')

  const toggleMode = () => {
    const next = mode === 'advanced' ? 'simple' : 'advanced'
    setMode(next)
    try {
      localStorage.setItem(MODE_KEY, next)
    } catch {
      // ignore
    }
  }

  const goDashboard = () => {
    setPreviousMode(mode)
    setMode('dashboard')
  }

  const backFromDashboard = () => {
    setMode(previousMode)
    try {
      localStorage.setItem(MODE_KEY, previousMode)
    } catch {
      // ignore
    }
  }

  return (
    <div className={styles.container}>
      {mode === 'advanced' && (
        <UARPanel onToggleMode={toggleMode} modeLabel="Simple" onGoDashboard={goDashboard} />
      )}
      {mode === 'simple' && (
        <UARSimplePanel onToggleMode={toggleMode} modeLabel="Advanced" onGoDashboard={goDashboard} />
      )}
      {mode === 'dashboard' && (
        <Dashboard onBack={backFromDashboard} modeLabel={previousMode === 'advanced' ? 'Advanced' : 'Simple'} />
      )}
    </div>
  )
}
