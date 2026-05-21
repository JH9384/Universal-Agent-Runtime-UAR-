import { useRef, useMemo, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import styles from './TrefoilKnotVisualizer.module.css'

interface TrefoilData {
  knots: [number, number, number][][]
  quaternions: [number, number, number, number][][]
  inverses: [number, number, number][][]
  core: [number, number, number][]
  equilibrium: boolean
  num_points: number
  num_trefoils: number
}

interface TrefoilKnotVisualizerProps {
  data: TrefoilData | null
  darkMode?: boolean
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

function Scene({ data }: { data: TrefoilData }) {
  return (
    <>
      <ambientLight intensity={0.5} />
      <pointLight position={[10, 10, 10]} />
      {data.knots.map((knot, i) => (
        <KnotTube
          key={i}
          points={knot}
          color={COLORS[i % COLORS.length]}
          inversePoints={data.inverses[i]}
        />
      ))}
      <CorePoints core={data.core} />
    </>
  )
}

export function TrefoilKnotVisualizer({
  data,
  darkMode = false,
}: TrefoilKnotVisualizerProps) {
  const [showInfo, setShowInfo] = useState(true)

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
        <button
          className={styles.toolbarButton}
          onClick={() => setShowInfo((s) => !s)}
          title="Toggle info panel"
        >
          ℹ️
        </button>
      </div>
      <div className={styles.canvasWrapper}>
        <Canvas camera={{ position: [8, 8, 8], fov: 50 }}>
          <Scene data={data} />
        </Canvas>
      </div>
      {showInfo && (
        <div className={styles.infoPanel}>
          <div>
            <strong>Trefoils:</strong> {data.num_trefoils}
          </div>
          <div>
            <strong>Points:</strong> {data.num_points}
          </div>
          <div>
            <strong>Equilibrium:</strong>{' '}
            {data.equilibrium ? '✅ Reached' : '❌ Not reached'}
          </div>
          <div className={styles.legend}>
            {COLORS.slice(0, data.num_trefoils).map((c, i) => (
              <span key={i} className={styles.legendItem}>
                <span
                  className={styles.legendDot}
                  style={{ background: c }}
                />
                Knot {i + 1}
              </span>
            ))}
            <span className={styles.legendItem}>
              <span
                className={styles.legendDot}
                style={{ background: '#ffffff' }}
              />
              Core
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
