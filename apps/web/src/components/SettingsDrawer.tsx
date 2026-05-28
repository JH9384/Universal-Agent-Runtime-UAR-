import { useRef, useEffect } from 'react'
import styles from './UARPanel.module.css'

interface SettingsDrawerProps {
  open: boolean
  onClose: () => void

  // Deployment mode
  deploymentMode: 'local' | 'shared'
  onDeploymentModeChange: (mode: 'local' | 'shared') => void

  // Auth
  apiKey: string
  onApiKeyChange: (key: string) => void

  // AI
  ollamaModel: string
  onOllamaModelChange: (m: string) => void

  // Execution
  useHierarchical: boolean
  onHierarchicalChange: (v: boolean) => void
  useWebSocket: boolean
  onUseWebSocketChange: (v: boolean) => void
  graphragMethod: 'local' | 'global'
  onGraphragMethodChange: (m: 'local' | 'global') => void

  // Storage
  autonomiKey: string
  onAutonomiKeyChange: (k: string) => void
  autonomiNetwork: 'testnet' | 'mainnet'
  onAutonomiNetworkChange: (n: 'testnet' | 'mainnet') => void
  autonomiPublic: boolean
  onAutonomiPublicChange: (v: boolean) => void
  autonomiAddress: string
  onAutonomiAddressChange: (addr: string) => void
}

export default function SettingsDrawer({
  open,
  onClose,
  deploymentMode,
  onDeploymentModeChange,
  apiKey,
  onApiKeyChange,
  ollamaModel,
  onOllamaModelChange,
  useHierarchical,
  onHierarchicalChange,
  graphragMethod,
  onGraphragMethodChange,
  useWebSocket,
  onUseWebSocketChange,
  autonomiKey,
  onAutonomiKeyChange,
  autonomiNetwork,
  onAutonomiNetworkChange,
  autonomiPublic,
  onAutonomiPublicChange,
  autonomiAddress,
  onAutonomiAddressChange,
}: SettingsDrawerProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className={styles.drawerOverlay}
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={ref}
        className={styles.drawerContent}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
      >
        <div className={styles.drawerHeader}>
          <strong>Settings</strong>
          <button
            onClick={onClose}
            className={styles.drawerClose}
            aria-label="Close settings"
          >
            ✕
          </button>
        </div>

        <div className={styles.drawerBody}>
          {/* Deployment Mode */}
          <div className={styles.drawerSection}>
            <div className={styles.modeLabel}>Deployment Mode</div>
            <div className={styles.modeCards}>
              <button
                className={`${styles.modeCard} ${deploymentMode === 'local' ? styles.modeCardActive : ''}`}
                onClick={() => onDeploymentModeChange('local')}
                aria-pressed={deploymentMode === 'local'}
                type="button"
              >
                <span className={styles.modeCardIcon}>🏠</span>
                <span className={styles.modeCardTitle}>Local</span>
                <span className={styles.modeCardDesc}>
                  Runs on your machine. No API key needed.
                </span>
              </button>
              <button
                className={`${styles.modeCard} ${deploymentMode === 'shared' ? styles.modeCardActive : ''}`}
                onClick={() => onDeploymentModeChange('shared')}
                aria-pressed={deploymentMode === 'shared'}
                type="button"
              >
                <span className={styles.modeCardIcon}>🌐</span>
                <span className={styles.modeCardTitle}>Shared</span>
                <span className={styles.modeCardDesc}>
                  Team server. API key required.
                </span>
              </button>
            </div>
            {deploymentMode === 'shared' && (
              <div className={styles.modeAlert}>
                <strong>API key required</strong> for all endpoints.
              </div>
            )}
          </div>

          {/* API Key */}
          <div className={styles.drawerSection}>
            <label className={styles.drawerLabel}>
              API Key
              {deploymentMode === 'local' && (
                <span className={styles.drawerHint}>
                  Optional in local mode
                </span>
              )}
              {deploymentMode === 'shared' && (
                <span className={styles.drawerHintRequired}>
                  Required
                </span>
              )}
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => onApiKeyChange(e.target.value)}
              placeholder={
                deploymentMode === 'local'
                  ? 'Optional — add if connecting to shared backend'
                  : 'Enter your API key'
              }
              className={styles.drawerInput}
            />
          </div>

          {/* AI Provider */}
          <div className={styles.drawerSection}>
            <div className={styles.drawerSectionTitle}>🤖 AI Provider</div>
            <label className={styles.drawerLabel}>
              Ollama Model
              <span className={styles.drawerHint}>
                Local AI — no external API needed
              </span>
            </label>
            <input
              type="text"
              value={ollamaModel}
              onChange={(e) => onOllamaModelChange(e.target.value)}
              placeholder="e.g. llama3.2:3b"
              className={styles.drawerInput}
            />
          </div>

          {/* Execution */}
          <div className={styles.drawerSection}>
            <div className={styles.drawerSectionTitle}>⚡ Execution</div>
            <div className={styles.drawerToggleRow}>
              <input
                type="checkbox"
                id="hierarchical"
                checked={useHierarchical}
                onChange={(e) => onHierarchicalChange(e.target.checked)}
              />
              <label htmlFor="hierarchical">
                Hierarchical mode
                <span className={styles.drawerHintInline}>
                  Recipes run as discrete units
                </span>
              </label>
            </div>
            <div className={styles.drawerToggleRow}>
              <input
                type="checkbox"
                id="websocket"
                checked={useWebSocket}
                onChange={(e) => onUseWebSocketChange(e.target.checked)}
              />
              <label htmlFor="websocket">
                WebSocket streaming
                <span className={styles.drawerHintInline}>
                  More resilient for long runs
                </span>
              </label>
            </div>
            <label className={styles.drawerLabel}>GraphRAG Method</label>
            <div className={styles.drawerToggleRow}>
              <label>
                <input
                  type="radio"
                  name="graphrag"
                  value="local"
                  checked={graphragMethod === 'local'}
                  onChange={() => onGraphragMethodChange('local')}
                />
                Local
              </label>
              <label>
                <input
                  type="radio"
                  name="graphrag"
                  value="global"
                  checked={graphragMethod === 'global'}
                  onChange={() => onGraphragMethodChange('global')}
                />
                Global
              </label>
            </div>
          </div>

          {/* Autonomi */}
          <div className={styles.drawerSection}>
            <div className={styles.drawerSectionTitle}>☁️ Autonomi Storage</div>
            <label className={styles.drawerLabel}>Private Key</label>
            <input
              type="password"
              value={autonomiKey}
              onChange={(e) => onAutonomiKeyChange(e.target.value)}
              placeholder="Optional — for decentralized uploads"
              className={styles.drawerInput}
            />
            <div className={styles.drawerToggleRow}>
              <label>
                <input
                  type="radio"
                  name="autonomiNet"
                  value="testnet"
                  checked={autonomiNetwork === 'testnet'}
                  onChange={() => onAutonomiNetworkChange('testnet')}
                />
                Testnet
              </label>
              <label>
                <input
                  type="radio"
                  name="autonomiNet"
                  value="mainnet"
                  checked={autonomiNetwork === 'mainnet'}
                  onChange={() => onAutonomiNetworkChange('mainnet')}
                />
                Mainnet
              </label>
            </div>
            <div className={styles.drawerToggleRow}>
              <input
                type="checkbox"
                id="autonomiPublic"
                checked={autonomiPublic}
                onChange={(e) => onAutonomiPublicChange(e.target.checked)}
              />
              <label htmlFor="autonomiPublic">Public uploads</label>
            </div>
            <label className={`${styles.drawerLabel} ${styles.drawerLabelSpaced}`}>
              Default Address
            </label>
            <input
              type="text"
              value={autonomiAddress}
              onChange={(e) => onAutonomiAddressChange(e.target.value)}
              placeholder="Autonomi address"
              className={styles.drawerInput}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
