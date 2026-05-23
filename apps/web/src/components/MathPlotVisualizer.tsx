import { useCallback, useState } from 'react'
import styles from './MathPlotVisualizer.module.css'

interface MathPlotData {
  success: boolean
  image_base64?: string
  format?: string
  plot_type?: string
  expressions?: string[]
  x_range?: number[]
  y_range?: number[] | null
  x_expression?: string
  y_expression?: string
  t_range?: number[]
  r_expression?: string
  theta_range?: number[]
  point_count?: number
  error?: string
}

interface MathPlotVisualizerProps {
  data: MathPlotData | null
  darkMode?: boolean
}

export function MathPlotVisualizer({
  data,
  darkMode = false,
}: MathPlotVisualizerProps) {
  const [zoomed, setZoomed] = useState(false)

  const handleDownload = useCallback(() => {
    if (!data?.image_base64) return
    const link = document.createElement('a')
    link.download = `math-plot-${data.plot_type || 'plot'}-${Date.now()}.png`
    link.href = `data:image/png;base64,${data.image_base64}`
    link.click()
  }, [data])

  if (!data) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.empty}>
          <p>Run the math_plot skill to generate plots.</p>
        </div>
      </div>
    )
  }

  if (!data.success || !data.image_base64) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.toolbar}>
          <span className={styles.title}>Math Plot</span>
        </div>
        <div className={styles.errorPanel}>
          <div className={styles.errorBadge}>Error</div>
          <p className={styles.errorText}>
            {data.error || 'Plot generation failed'}
          </p>
        </div>
      </div>
    )
  }

  const typeLabel = data.plot_type
    ? data.plot_type.charAt(0).toUpperCase() + data.plot_type.slice(1)
    : 'Plot'

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      <div className={styles.toolbar}>
        <span className={styles.title}>{typeLabel} Plot</span>
        <div className={styles.toolbarButtons}>
          <button
            className={styles.toolbarButton}
            onClick={() => setZoomed((z) => !z)}
            title={zoomed ? 'Shrink' : 'Expand'}
          >
            {zoomed ? '⛶' : '⛶'}
          </button>
          <button
            className={styles.toolbarButton}
            onClick={handleDownload}
            title="Download PNG"
          >
            📥
          </button>
        </div>
      </div>

      <div
        className={`${styles.imageWrapper} ${zoomed ? styles.zoomed : ''}`}
        onClick={() => setZoomed((z) => !z)}
      >
        <img
          src={`data:image/png;base64,${data.image_base64}`}
          alt={`${typeLabel} plot`}
          className={styles.plotImage}
        />
      </div>

      <div className={styles.metaPanel}>
        {data.expressions && data.expressions.length > 0 && (
          <div className={styles.metaRow}>
            <span className={styles.metaLabel}>Expressions:</span>
            <code className={styles.metaCode}>
              {data.expressions.join(', ')}
            </code>
          </div>
        )}
        {data.x_expression && data.y_expression && (
          <div className={styles.metaRow}>
            <span className={styles.metaLabel}>Parametric:</span>
            <code className={styles.metaCode}>
              x = {data.x_expression}, y = {data.y_expression}
            </code>
          </div>
        )}
        {data.r_expression && (
          <div className={styles.metaRow}>
            <span className={styles.metaLabel}>Polar:</span>
            <code className={styles.metaCode}>
              r = {data.r_expression}
            </code>
          </div>
        )}
        {data.x_range && (
          <div className={styles.metaRow}>
            <span className={styles.metaLabel}>X range:</span>
            <code className={styles.metaCode}>
              [{data.x_range[0]}, {data.x_range[1]}]
            </code>
          </div>
        )}
        {data.y_range && (
          <div className={styles.metaRow}>
            <span className={styles.metaLabel}>Y range:</span>
            <code className={styles.metaCode}>
              [{data.y_range[0]}, {data.y_range[1]}]
            </code>
          </div>
        )}
        {data.point_count !== undefined && (
          <div className={styles.metaRow}>
            <span className={styles.metaLabel}>Points:</span>
            <code className={styles.metaCode}>{data.point_count}</code>
          </div>
        )}
      </div>
    </div>
  )
}
