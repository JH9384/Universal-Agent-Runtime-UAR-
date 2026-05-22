import { useMemo, useRef, useCallback } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import { useCanvasRecorder } from '../hooks/useCanvasRecorder'
import styles from './DataViz3D.module.css'

interface MeshData {
  mesh_type: string
  vertices: number[][]
  normals: number[][]
  uvs: number[][]
  indices: number[]
  vertex_count: number
  face_count: number
}

interface DataViz3DProps {
  data: MeshData | null
  darkMode?: boolean
}

function MeshGeometry({ data }: { data: MeshData }) {
  const meshRef = useRef<THREE.Mesh>(null)

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry()
    const verts = new Float32Array(data.vertices.flat())
    const norms = new Float32Array(data.normals.flat())
    const idx = new Uint16Array(data.indices)

    geo.setAttribute('position', new THREE.BufferAttribute(verts, 3))
    geo.setAttribute('normal', new THREE.BufferAttribute(norms, 3))
    geo.setIndex(new THREE.BufferAttribute(idx, 1))
    geo.computeBoundingSphere()
    return geo
  }, [data])

  return (
    <mesh ref={meshRef} geometry={geometry}>
      <meshStandardMaterial
        color="#60a5fa"
        roughness={0.4}
        metalness={0.3}
        wireframe={false}
        side={THREE.DoubleSide}
      />
      <meshStandardMaterial
        color="#1e293b"
        roughness={0.1}
        metalness={0.1}
        wireframe
        transparent
        opacity={0.15}
      />
    </mesh>
  )
}

function WireframeOnly({ data }: { data: MeshData }) {
  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry()
    const verts = new Float32Array(data.vertices.flat())
    const idx = new Uint16Array(data.indices)
    geo.setAttribute('position', new THREE.BufferAttribute(verts, 3))
    geo.setIndex(new THREE.BufferAttribute(idx, 1))
    return geo
  }, [data])

  return (
    <mesh geometry={geometry}>
      <meshBasicMaterial color="#60a5fa" wireframe />
    </mesh>
  )
}

function Scene({ data }: { data: MeshData }) {
  return (
    <>
      <ambientLight intensity={0.4} />
      <directionalLight position={[5, 5, 5]} intensity={1} />
      <directionalLight position={[-5, -3, -5]} intensity={0.3} />
      <WireframeOnly data={data} />
      <OrbitControls enablePan enableZoom enableRotate />
    </>
  )
}

export function DataViz3D({ data, darkMode = false }: DataViz3DProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const { startRecording, stopRecording, state: recState, error: recError } = useCanvasRecorder(canvasRef, 30)

  const handleExport = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const link = document.createElement('a')
    link.download = `mesh-${data?.mesh_type || 'unknown'}-${Date.now()}.png`
    link.href = canvas.toDataURL('image/png')
    link.click()
  }, [data])

  if (!data) {
    return (
      <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
        <div className={styles.empty}>
          <p>Run the data_viz_3d skill to generate mesh data.</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`${styles.container} ${darkMode ? styles.dark : ''}`}>
      <div className={styles.toolbar}>
        <span className={styles.title}>
          🧊 {data.mesh_type} ({data.vertex_count.toLocaleString()} vertices,{' '}
          {data.face_count.toLocaleString()} faces)
        </span>
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
        </div>
        {recError && <span className={styles.recError}>{recError}</span>}
      </div>
      <div className={styles.canvasWrapper}>
        <Canvas
          camera={{ position: [2, 2, 2], fov: 50 }}
          gl={{ preserveDrawingBuffer: true }}
          onCreated={({ gl }) => { canvasRef.current = gl.domElement as HTMLCanvasElement }}
        >
          <Scene data={data} />
        </Canvas>
      </div>
    </div>
  )
}
