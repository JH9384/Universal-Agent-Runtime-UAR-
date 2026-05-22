import { useRef, useMemo, useState, useCallback } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useCanvasRecorder } from '../hooks/useCanvasRecorder'
import styles from './QuantumCircuitVisualizer.module.css'

interface CircuitGate {
  type: string
  shape: string
  color: string
  position: [number, number, number]
  qubit: number
  step: number
  size: number
}

interface QuantumCircuitData {
  qubits: number
  depth: number
  qubit_tracks: [number, number, number][]
  gates: CircuitGate[]
  connections: [number, number, number, number][]
  gate_count: number
}

interface QuantumCircuitVisualizerProps {
  data: QuantumCircuitData | null
  darkMode?: boolean
}

function GateMesh({ gate }: { gate: CircuitGate }) {
  const meshRef = useRef<THREE.Mesh>(null)

  useFrame((_, delta) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += delta * 0.5
    }
  })

  const geometry = useMemo(() => {
    const s = gate.size
    switch (gate.shape) {
      case 'sphere':
        return new THREE.SphereGeometry(s, 24, 24)
      case 'cube':
        return new THREE.BoxGeometry(s * 1.5, s * 1.5, s * 1.5)
      case 'cylinder':
        return new THREE.CylinderGeometry(s * 0.5, s * 0.5, s * 2, 16)
      case 'pyramid':
        return new THREE.ConeGeometry(s, s * 1.5, 4)
      case 'octahedron':
        return new THREE.OctahedronGeometry(s)
      case 'tetrahedron':
        return new THREE.TetrahedronGeometry(s)
      case 'double_cone':
        return new THREE.ConeGeometry(s * 0.6, s, 16)
      case 'ring':
        return new THREE.TorusGeometry(s * 0.8, s * 0.15, 12, 24)
      default:
        return new THREE.BoxGeometry(s, s, s)
    }
  }, [gate.shape, gate.size])

  return (
    <mesh ref={meshRef} geometry={geometry} position={gate.position}>
      <meshStandardMaterial
        color={gate.color}
        metalness={0.5}
        roughness={0.3}
        transparent={gate.type === 'control'}
        opacity={gate.type === 'control' ? 0.6 : 1.0}
      />
    </mesh>
  )
}

function ConnectionLine({
  start,
  end,
}: {
  start: [number, number, number]
  end: [number, number, number]
}) {
  const { position, rotation, height } = useMemo(() => {
    const s = new THREE.Vector3(...start)
    const e = new THREE.Vector3(...end)
    const mid = new THREE.Vector3().addVectors(s, e).multiplyScalar(0.5)
    const diff = new THREE.Vector3().subVectors(e, s)
    const len = diff.length()
    const axis = new THREE.Vector3(0, 1, 0)
    const quat = new THREE.Quaternion().setFromUnitVectors(axis, diff.normalize())
    const euler = new THREE.Euler().setFromQuaternion(quat)
    return {
      position: mid.toArray() as [number, number, number],
      rotation: euler,
      height: len,
    }
  }, [start, end])

  return (
    <mesh position={position} rotation={rotation}>
      <cylinderGeometry args={[0.02, 0.02, height, 6]} />
      <meshStandardMaterial color="#a855f7" transparent opacity={0.6} />
    </mesh>
  )
}

function QubitTrack({ position }: { position: [number, number, number] }) {
  return (
    <mesh position={position}>
      <boxGeometry args={[0.02, 0.02, 4]} />
      <meshStandardMaterial color="#64748b" transparent opacity={0.4} />
    </mesh>
  )
}

function Scene({ data }: { data: QuantumCircuitData }) {
  const groupRef = useRef<THREE.Group>(null)

  useFrame((_, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.08
    }
  })

  const trackMap = useMemo(() => {
    const map = new Map<number, [number, number, number]>()
    data.qubit_tracks.forEach((t, i) => map.set(i, t))
    return map
  }, [data.qubit_tracks])

  return (
    <group ref={groupRef}>
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} intensity={1.0} />
      <pointLight position={[-10, -5, -5]} intensity={0.3} />
      {data.qubit_tracks.map((track, i) => (
        <QubitTrack key={`track-${i}`} position={track} />
      ))}
      {data.gates.map((gate, i) => (
        <GateMesh key={`gate-${i}`} gate={gate} />
      ))}
      {data.connections.map((conn, i) => {
        const c1 = trackMap.get(conn[0])
        const c2 = trackMap.get(conn[1])
        if (!c1 || !c2) return null
        const step = conn[2]
        const x = (step - data.depth / 2) * 2.0
        return (
          <ConnectionLine
            key={`conn-${i}`}
            start={[x, c1[1], 0.2]}
            end={[x, c2[1], 0.2]}
          />
        )
      })}
    </group>
  )
}

function computeCameraPosition(qubits: number, depth: number): [number, number, number] {
  const maxDim = Math.max(qubits * 2, depth * 2, 4)
  const dist = maxDim * 1.2
  return [dist, dist * 0.5, dist]
}

export function QuantumCircuitVisualizer({
  data,
  darkMode = false,
}: QuantumCircuitVisualizerProps) {
  const [showInfo, setShowInfo] = useState(true)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const { startRecording, stopRecording, state: recState, error: recError } = useCanvasRecorder(canvasRef, 30)

  const handleExport = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const link = document.createElement('a')
    link.download = `quantum-circuit-${Date.now()}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  }, [])

  const cameraPos = useMemo(
    () => (data ? computeCameraPosition(data.qubits, data.depth) : [8, 4, 8] as [number, number, number]),
    [data]
  )

  if (!data) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.empty}>
          <p>Run the quantum_circuit_visualization skill to generate 3D data.</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      <div className={styles.toolbar}>
        <span className={styles.title}>Quantum Circuit</span>
        <div className={styles.toolbarButtons}>
          <button
            className={`${styles.toolbarButton} ${recState.isRecording ? styles.recording : ''}`}
            onClick={recState.isRecording ? stopRecording : startRecording}
            title={recState.isRecording ? `Stop recording (${recState.recordedSeconds}s)` : 'Record video'}
          >
            {recState.isRecording ? `⏹ ${recState.recordedSeconds}s` : '🎥'}
          </button>
          <button className={styles.toolbarButton} onClick={handleExport} title="Export PNG frame">
            📷
          </button>
          <button className={styles.toolbarButton} onClick={() => setShowInfo((s) => !s)} title="Toggle info panel">
            ℹ️
          </button>
        </div>
        {recError && <span className={styles.recError}>{recError}</span>}
      </div>
      <div className={styles.canvasWrapper}>
        <Canvas
          camera={{ position: cameraPos, fov: 50 }}
          gl={{ preserveDrawingBuffer: true }}
          onCreated={({ gl }) => { canvasRef.current = gl.domElement as HTMLCanvasElement }}
        >
          <Scene data={data} />
        </Canvas>
      </div>
      {showInfo && (
        <div className={styles.infoPanel}>
          <div className={styles.infoGrid}>
            <div><strong>Qubits:</strong> {data.qubits}</div>
            <div><strong>Depth:</strong> {data.depth}</div>
            <div><strong>Gates:</strong> {data.gate_count}</div>
            <div><strong>Entanglements:</strong> {data.connections.length}</div>
          </div>
          <div className={styles.legend}>
            {Array.from(new Set(data.gates.map((g) => g.type))).map((t) => (
              <span key={t} className={styles.legendItem}>
                <span
                  className={styles.legendDot}
                  style={{ backgroundColor: data.gates.find((g) => g.type === t)?.color || '#888' }}
                />
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
