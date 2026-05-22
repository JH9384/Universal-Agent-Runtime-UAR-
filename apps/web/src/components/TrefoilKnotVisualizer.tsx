import { useRef, useMemo, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useCanvasRecorder } from '../hooks/useCanvasRecorder'
import styles from './TrefoilKnotVisualizer.module.css'

interface Keyframe {
  frame: number
  knots: [number, number, number][][]
  time: number
}

interface TrefoilData {
  knots: [number, number, number][][]
  quaternions: [number, number, number, number][][]
  inverses: [number, number, number][][]
  core: [number, number, number][]
  equilibrium: boolean
  num_points: number
  num_trefoils: number
  keyframes: Keyframe[]
  expansion: number
  torsional_sync: number
  twistor_strength: number
  phase_lock_mode: string
  phase_lock_strength: number
  rotation_speed: number
}

interface TrefoilKnotVisualizerProps {
  data: TrefoilData | null
  darkMode?: boolean
  onParamChange?: (key: string, value: number | string) => void
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b']

function KnotTube({
  points,
  color,
  inversePoints,
}: {
  points: [number, number, number][]
  color: string
  inversePoints: [number, number, number][]
}) {
  const groupRef = useRef<THREE.Group>(null)

  const tubeGeo = useMemo(() => {
    const curve = new THREE.CatmullRomCurve3(
      points.map((p) => new THREE.Vector3(p[0], p[1], p[2]))
    )
    curve.closed = true
    return new THREE.TubeGeometry(curve, 256, 0.04, 8, true)
  }, [points])

  const invTubeGeo = useMemo(() => {
    const curve = new THREE.CatmullRomCurve3(
      inversePoints.map((p) => new THREE.Vector3(p[0], p[1], p[2]))
    )
    curve.closed = true
    return new THREE.TubeGeometry(curve, 256, 0.02, 8, true)
  }, [inversePoints])

  useFrame((_, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.2
      groupRef.current.rotation.x += delta * 0.1
    }
  })

  return (
    <group ref={groupRef}>
      <mesh geometry={tubeGeo}>
        <meshStandardMaterial color={color} metalness={0.6} roughness={0.3} />
      </mesh>
      <mesh geometry={invTubeGeo}>
        <meshStandardMaterial
          color={color}
          transparent
          opacity={0.25}
          metalness={0.3}
          roughness={0.7}
        />
      </mesh>
    </group>
  )
}

function CorePoints({ core }: { core: [number, number, number][] }) {
  const points = useMemo(
    () => core.map((p) => new THREE.Vector3(p[0], p[1], p[2])),
    [core]
  )
  const geometry = useMemo(
    () => new THREE.BufferGeometry().setFromPoints(points),
    [points]
  )

  return (
    <points geometry={geometry}>
      <pointsMaterial color="#ffffff" size={0.05} sizeAttenuation />
    </points>
  )
}

function AnimatedScene({
  data,
  animating,
}: {
  data: TrefoilData
  animating: boolean
}) {
  const [frameIdx, setFrameIdx] = useState(0)
  const frameRef = useRef(0)
  const lastTime = useRef(0)

  useFrame((state) => {
    if (!animating || data.keyframes.length === 0) return
    const now = state.clock.elapsedTime
    if (now - lastTime.current < 0.033) return  // ~30fps
    lastTime.current = now
    frameRef.current = (frameRef.current + 1) % data.keyframes.length
    setFrameIdx(frameRef.current)
  })

  const displayData = animating && data.keyframes.length > 0
    ? {
        knots: data.keyframes[frameIdx].knots,
        inverses: data.inverses,
        core: data.core,
        num_trefoils: data.num_trefoils,
      }
    : data

  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} />
      {displayData.knots.map((knot, i) => (
        <KnotTube
          key={i}
          points={knot}
          color={COLORS[i % COLORS.length]}
          inversePoints={displayData.inverses[i] || []}
        />
      ))}
      <CorePoints core={displayData.core} />
    </>
  )
}

export function TrefoilKnotVisualizer({
  data,
  darkMode = false,
  onParamChange,
}: TrefoilKnotVisualizerProps) {
  const [showInfo, setShowInfo] = useState(true)
  const [animating, setAnimating] = useState(false)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const { startRecording, stopRecording, state: recState, error: recError } = useCanvasRecorder(canvasRef, 30)

  const handleExport = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    const link = document.createElement('a')
    link.download = `trefoil-${Date.now()}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  }

  if (!data) {
    return (
      <div
        className={`${styles.container} ${darkMode ? styles.dark : ''}`}
      >
        <div className={styles.empty}>
          <p>Run the trefoil_simulation skill to generate 3D data.</p>
        </div>
      </div>
    )
  }

  return (
    <div
      className={`${styles.container} ${darkMode ? styles.dark : ''}`}
    >
      <div className={styles.toolbar}>
        <span className={styles.title}>Triple Trefoil Quaternion Equilibrium</span>
        <div className={styles.toolbarButtons}>
          <button
            className={`${styles.toolbarButton} ${recState.isRecording ? styles.recording : ''}`}
            onClick={recState.isRecording ? stopRecording : startRecording}
            title={recState.isRecording ? `Stop recording (${recState.recordedSeconds}s)` : 'Record video'}
          >
            {recState.isRecording ? `⏹ ${recState.recordedSeconds}s` : '🎥'}
          </button>
          <button
            className={styles.toolbarButton}
            onClick={() => setAnimating((a) => !a)}
            title={animating ? 'Stop animation' : 'Play keyframe animation'}
          >
            {animating ? '⏹️' : '▶️'}
          </button>
          <button
            className={styles.toolbarButton}
            onClick={handleExport}
            title="Export PNG frame"
          >
            📷
          </button>
          <button
            className={styles.toolbarButton}
            onClick={() => setShowInfo((s) => !s)}
            title="Toggle info panel"
          >
            ℹ️
          </button>
        </div>
        {recError && <span className={styles.recError}>{recError}</span>}
      </div>
      <div className={styles.canvasWrapper}>
        <Canvas
          camera={{ position: [8, 8, 8], fov: 50 }}
          gl={{ preserveDrawingBuffer: true }}
          onCreated={({ gl }) => {
            canvasRef.current = gl.domElement as HTMLCanvasElement
          }}
        >
          <AnimatedScene data={data} animating={animating} />
        </Canvas>
      </div>
      {showInfo && (
        <div className={styles.infoPanel}>
          <div className={styles.infoGrid}>
            <div><strong>Trefoils:</strong> {data.num_trefoils}</div>
            <div><strong>Points:</strong> {data.num_points}</div>
            <div><strong>Keyframes:</strong> {data.keyframes?.length || 0}</div>
            <div>
              <strong>Equilibrium:</strong>{' '}
              {data.equilibrium ? '✅ Reached' : '❌ Not reached'}
            </div>
            <div><strong>Expansion:</strong> {data.expansion?.toFixed(2) || '1.00'}</div>
            <div><strong>Torsional Sync:</strong> {data.torsional_sync?.toFixed(2) || '0.00'}</div>
            <div><strong>Twistor:</strong> {data.twistor_strength?.toFixed(2) || '0.00'}</div>
            <div><strong>Phase Lock:</strong> {data.phase_lock_mode || 'free'} ({data.phase_lock_strength?.toFixed(2) || '0.00'})</div>
          </div>
          <div className={styles.legend}>
            {COLORS.slice(0, data.num_trefoils).map((c, i) => (
              <span key={i} className={styles.legendItem}>
                <span
                  className={`${styles.legendDot} ${styles[`dotColor${i}`] || ''}`}
                />
                Knot {i + 1}
              </span>
            ))}
            <span className={styles.legendItem}>
              <span className={`${styles.legendDot} ${styles.dotCore}`} />
              Core
            </span>
          </div>
          {onParamChange && (
            <div className={styles.controls}>
              <label className={styles.controlLabel}>
                Expansion
                <input
                  type="range"
                  min="0.5"
                  max="3"
                  step="0.1"
                  defaultValue={data.expansion || 1}
                  onChange={(e) => onParamChange('expansion', parseFloat(e.target.value))}
                  className={styles.slider}
                />
              </label>
              <label className={styles.controlLabel}>
                Rotation Speed
                <input
                  type="range"
                  min="0"
                  max="5"
                  step="0.1"
                  defaultValue={data.rotation_speed || 1}
                  onChange={(e) => onParamChange('rotation_speed', parseFloat(e.target.value))}
                  className={styles.slider}
                />
              </label>
              <label className={styles.controlLabel}>
                Torsional Sync
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  defaultValue={data.torsional_sync || 0}
                  onChange={(e) => onParamChange('torsional_sync', parseFloat(e.target.value))}
                  className={styles.slider}
                />
              </label>
              <label className={styles.controlLabel}>
                Twistor Strength
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  defaultValue={data.twistor_strength || 0}
                  onChange={(e) => onParamChange('twistor_strength', parseFloat(e.target.value))}
                  className={styles.slider}
                />
              </label>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
