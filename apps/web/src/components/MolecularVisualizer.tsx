import { useRef, useMemo, useState, useCallback } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { useCanvasRecorder } from '../hooks/useCanvasRecorder'
import styles from './MolecularVisualizer.module.css'

interface Atom {
  element: string
  x: number
  y: number
  z: number
  radius: number
  color: string
}

interface Bond {
  from: number
  to: number
  distance: number
}

interface MolecularData {
  atoms: Atom[]
  bonds: [number, number, number][]
  molecule: string
  atom_count: number
  bond_count: number
}

interface MolecularVisualizerProps {
  data: MolecularData | null
  darkMode?: boolean
}

function AtomSphere({ atom }: { atom: Atom }) {
  const meshRef = useRef<THREE.Mesh>(null)

  useFrame((_, delta) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += delta * 0.3
    }
  })

  return (
    <mesh ref={meshRef} position={[atom.x, atom.y, atom.z]}>
      <sphereGeometry args={[atom.radius * 0.5, 32, 32]} />
      <meshStandardMaterial
        color={atom.color}
        metalness={0.4}
        roughness={0.4}
      />
    </mesh>
  )
}

function BondCylinder({
  a1,
  a2,
}: {
  a1: Atom
  a2: Atom
}) {
  const { position, rotation, height } = useMemo(() => {
    const start = new THREE.Vector3(a1.x, a1.y, a1.z)
    const end = new THREE.Vector3(a2.x, a2.y, a2.z)
    const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5)
    const diff = new THREE.Vector3().subVectors(end, start)
    const len = diff.length()
    const axis = new THREE.Vector3(0, 1, 0)
    const quat = new THREE.Quaternion().setFromUnitVectors(
      axis,
      diff.normalize()
    )
    const euler = new THREE.Euler().setFromQuaternion(quat)
    return { position: mid.toArray() as [number, number, number], rotation: euler, height: len }
  }, [a1, a2])

  return (
    <mesh position={position} rotation={rotation}>
      <cylinderGeometry args={[0.06, 0.06, height, 8]} />
      <meshStandardMaterial color="#888888" metalness={0.3} roughness={0.6} />
    </mesh>
  )
}

function Scene({ data }: { data: MolecularData }) {
  const groupRef = useRef<THREE.Group>(null)

  useFrame((_, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.15
    }
  })

  const atomMap = useMemo(() => {
    const map = new Map<number, Atom>()
    data.atoms.forEach((a, i) => map.set(i, a))
    return map
  }, [data.atoms])

  return (
    <group ref={groupRef}>
      <ambientLight intensity={0.6} />
      <pointLight position={[10, 10, 10]} intensity={1.2} />
      <pointLight position={[-10, -5, -5]} intensity={0.4} />
      {data.atoms.map((atom, i) => (
        <AtomSphere key={`atom-${i}`} atom={atom} />
      ))}
      {data.bonds.map((bond, i) => {
        const a1 = atomMap.get(bond[0])
        const a2 = atomMap.get(bond[1])
        if (!a1 || !a2) return null
        return <BondCylinder key={`bond-${i}`} a1={a1} a2={a2} />
      })}
    </group>
  )
}

function computeCameraPosition(atoms: Atom[]): [number, number, number] {
  if (atoms.length === 0) return [5, 5, 5]
  const maxDist = Math.max(
    ...atoms.map((a) => Math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z))
  )
  const dist = Math.max(maxDist * 2.5, 3)
  return [dist, dist * 0.6, dist]
}

export function MolecularVisualizer({
  data,
  darkMode = false,
}: MolecularVisualizerProps) {
  const [showInfo, setShowInfo] = useState(true)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const { startRecording, stopRecording, state: recState, error: recError } = useCanvasRecorder(canvasRef, 30)

  const handleExport = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const link = document.createElement('a')
    link.download = `molecule-${data?.molecule || 'unknown'}-${Date.now()}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  }, [data])

  const cameraPos = useMemo(
    () => (data ? computeCameraPosition(data.atoms) : [5, 5, 5] as [number, number, number]),
    [data]
  )

  if (!data) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.empty}>
          <p>Run the molecular_visualization skill to generate 3D data.</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      <div className={styles.toolbar}>
        <span className={styles.title}>{data.molecule.charAt(0).toUpperCase() + data.molecule.slice(1)} Molecule</span>
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
            <div><strong>Molecule:</strong> {data.molecule}</div>
            <div><strong>Atoms:</strong> {data.atom_count}</div>
            <div><strong>Bonds:</strong> {data.bond_count}</div>
          </div>
          <div className={styles.legend}>
            {Array.from(new Set(data.atoms.map((a) => a.element))).map((el) => (
              <span key={el} className={styles.legendItem}>
                <span
                  className={styles.legendDot}
                  style={{ backgroundColor: data.atoms.find((a) => a.element === el)?.color || '#888' }}
                />
                {el}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
