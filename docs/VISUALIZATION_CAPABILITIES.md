# UAR Visual & Graphics Capability Review

**Scope:** Complete inventory of all visualization, rendering, and graphics
components across the UAR frontend and backend.

**Last reviewed:** 2026-05-20

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Frontend (React + TypeScript)                      │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────┐  │
│  │ 3D (R3F)    │  │ 2D Graph     │  │ Metrics     │  │ UI Shell │  │
│  │ Trefoil     │  │ ReactFlow    │  │ Dashboard   │  │ Panel    │  │
│  └─────────────┘  └──────────────┘  └─────────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                    WebSocket / REST
                              │
┌─────────────────────────────────────────────────────────────────────┐
│                      Backend (Python / FastAPI)                     │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Simulation  │  │ Simulation   │  │ Simulation   │               │
│  │ Skills      │  │ Skills       │  │ Skills       │               │
│  │ (trefoil)   │  │ (molecular)  │  │ (quantum)    │               │
│  └─────────────┘  └──────────────┘  └──────────────┘               │
│  ┌────────────────────────────────────────────────────┐             │
│  │ Binary Stream Serializer (binary_stream.py)        │             │
│  └────────────────────────────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

Interactive architecture diagram:
[UAR Full Visual & Graphics Architecture](https://www.figma.com/board/TzNMaSbOvIdtHwhbTt2xe1)

---

## 2. Frontend Visualization Components

### 2.1 TrefoilKnotVisualizer — 3D React Three Fiber

**File:** `apps/web/src/components/TrefoilKnotVisualizer.tsx`
**Styling:** `TrefoilKnotVisualizer.module.css`

| Capability | Implementation |
|---|---|
| **Renderer** | `@react-three/fiber` Canvas with `preserveDrawingBuffer: true` |
| **Geometry** | `THREE.TubeGeometry` via `CatmullRomCurve3` (closed, 256 segments) |
| **Knot tubes** | 3 trefoil knots with colors `#3b82f6`, `#10b981`, `#f59e0b` |
| **Inverse tubes** | Ghost streams at 25% opacity, 0.02 radius |
| **Core points** | `THREE.Points` with white `pointsMaterial`, size 0.05 |
| **Animation** | `AnimatedScene` component — `useFrame` at ~30fps |
| **Keyframes** | 60 pre-computed quaternion-interpolated frames |
| **Auto-rotation** | Continuous Y (0.2 rad/s) + X (0.1 rad/s) on group |
| **PNG Export** | `canvas.toDataURL('image/png')` via download link |
| **Interactive sliders** | Expansion, rotation_speed, torsional_sync, twistor_strength |
| **Info panel** | Parameters grid + color legend + equilibrium status |

**TypeScript interfaces:**
```typescript
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
```

---

### 2.2 GraphVisualizer — 2D ReactFlow

**File:** `apps/web/src/components/GraphVisualizer.tsx`
**Styling:** `GraphVisualizer.module.css`

| Capability | Implementation |
|---|---|
| **Renderer** | `reactflow` with `Background`, `Controls`, `MiniMap` |
| **Layout** | Force-directed + tree-aware hybrid (custom `computeLayout`) |
| **Nodes** | Custom node types: `default`, `skill`, `recipe`, `start`, `end` |
| **Edges** | Animated flow edges with `MarkerType.ArrowClosed` |
| **PNG export** | `html-to-image` `toPng()` capture |
| **Interactivity** | Drag, zoom, pan, selection, edge highlighting |
| **Data model** | `GraphNode` / `GraphEdge` with extensible metadata |

---

### 2.3 MetricsDashboard

**File:** `apps/web/src/components/MetricsDashboard.tsx`
**Styling:** `MetricsDashboard.module.css`

| Capability | Implementation |
|---|---|
| **Skill timing** | Sorted bar list of `skill_times_ms` |
| **Cache stats** | Hit/miss counts + percentage rate |
| **Recipe cache** | Separate recipe cache hit/miss tracking |
| **Duration formatting** | `<1s` → ms, `<60s` → s, else `m:s` |

---

### 2.4 Supporting UI Components

| Component | File | Role |
|---|---|---|
| **UARPanel** | `UARPanel.tsx` | Main orchestration hub; manages state for all visualizers; WebSocket event handling; skill/recipe selection; trefoilData state |
| **SkillGuide** | `SkillGuide.tsx` | Skill documentation panel with parameter descriptions |
| **FilePicker** | `FilePicker.tsx` | File selection with presets |
| **RecipeTimeline** | `RecipeTimeline.tsx` | Step-by-step recipe execution tracking |

---

## 3. Backend Simulation Skills

### 3.1 trefoil_simulation

**File:** `uar/skills/trefoil_simulation.py`

| Math / Physics | Implementation |
|---|---|
| **Curve basis** | Parametric trefoil: `r(t) = [sin(t)+2sin(2t), cos(t)-2cos(2t), -sin(3t)]` |
| **Clifford torus** | Dual-radius embedding `(R=2.0, r=0.6)` scaled by `expansion` factor |
| **Frenet frames** | Tangent, Normal, Binormal computed via finite differences |
| **Quaternions** | Frenet frame → quaternion; `axis-angle` → `w,x,y,z` |
| **SLERP** | `slerp(q1, q2, t)` with shortest-path sign correction and normalization |
| **Twistor transform** | Penrose bundle: complex rotation in x-y, half-phase z modulation |
| **Torsional sync** | Blend factor `0=free rotation, 1=locked phases` across trefoils |
| **Phase locking** | Modes: `free`, `locked`, `anti` with blendable `phase_lock_strength` |
| **Expansion** | Scales Clifford torus `(R, r)` radii |
| **Keyframes** | 60 frames via quaternion interpolation; sparse point sampling |
| **Equilibrium** | Detected when `‖core‖ < ε` (emergent singularity core vector sum) |

**Parameters (all have defaults):**
```python
num_points=256, num_trefoils=3, rotation_speed=1.0,
expansion=1.0, torsional_sync=0.0, twistor_strength=0.0,
phase_lock_mode="free", phase_lock_strength=0.0,
generate_keyframes=True, num_keyframes=60
```

---

### 3.2 molecular_visualization

**File:** `uar/skills/molecular_visualization.py`

| Capability | Implementation |
|---|---|
| **Preset molecules** | `water`, `methane`, `benzene`, `caffeine` (Angstrom coordinates) |
| **Protein backbone** | Alpha-helix generator: 100°/residue, 2.3Å radius, 1.5Å rise |
| **Bond detection** | Distance threshold: `dist < (r1 + r2) × 1.3` |
| **CPK colors** | H=white, C=#333, N=#3050f8, O=#ff0d0d, F/P/S/Cl |
| **CPK radii** | H=0.31Å, C=0.76Å, N=0.71Å, O=0.66Å |
| **Centering** | Centroid subtraction for origin-centered display |

**Parameters:**
```python
molecule="water", residues=10
```

---

### 3.3 quantum_circuit_visualization

**File:** `uar/skills/quantum_circuit_visualization.py`

| Capability | Implementation |
|---|---|
| **Gate shapes** | H=cube, X=octahedron, Y=diamond, Z=tetrahedron, CNOT=sphere, RX/RY/RZ=cylinder, T/S=pyramid, SWAP=double_cone, MEASURE=ring |
| **Gate colors** | Distinct palette per gate type (Tailwind-inspired) |
| **Qubit layout** | Tracks along Y axis, spaced 2.0 units |
| **Gate placement** | X position = `(step - depth/2) × 2.0` |
| **Control dots** | White spheres (0.15 radius) for multi-qubit gates |
| **Entanglement** | Connection tuples `(control, target, step, step)` |
| **Default circuit** | Bell/GHZ: Hadamard + CNOT chain + RZ rotations + measurements |

**Parameters:**
```python
qubits=4, depth=8, gate_sequence=None
```

---

## 4. Binary Streaming Infrastructure

**File:** `uar/core/binary_stream.py`

### 4.1 Core Packing Functions

| Function | Format | Purpose |
|---|---|---|
| `pack_floats()` | `struct.pack("<{n}d", ...)` | IEEE 754 double array |
| `unpack_floats()` | `struct.unpack("<{n}d", ...)` | Decode double array |
| `pack_points()` | Flat `[x,y,z, x,y,z, ...]` | 3D point clouds |
| `pack_quaternions()` | Flat `[w,x,y,z, w,x,y,z, ...]` | Quaternion arrays |

### 4.2 Skill-Specific Serializers

| Serializer | Chunks | Metadata Header |
|---|---|---|
| `serialize_trefoil` | `knot_0`, `knot_1`, `knot_2`, `core` | `<4i4d>`: num_points, num_trefoils, keyframe_count, equilibrium_flag, expansion, torsional_sync, twistor_strength, phase_lock_strength |
| `serialize_molecular` | `atoms` (x,y,z,radius), `bonds` (i,j,dist) | `<2i>`: atom_count, bond_count |
| `serialize_quantum_circuit` | `tracks` (x,y,z), `gates` (x,y,z,size) | `<3i>`: qubits, depth, gate_count |

### 4.3 WebSocket Integration

**File:** `uar/api/server.py`

| Integration Point | Behavior |
|---|---|
| `_stream_binary_visualization()` | Auto-detects viz skills; sends binary after `skill_complete` JSON |
| **Direct WS handler** | `stream_goal_ws()` — binary sent inline after each `skill_complete` |
| **Batch WS handler** | `stream_goal_ws` variant — binary sent during `_flush_batch()` per event |
| **Frame format** | `name.encode() + b"\x00" + binary_payload` |
| **Error handling** | Best-effort; exceptions silently caught; JSON event already delivered |

---

## 5. Data Flow: Visualization Lifecycle

```
1. User selects skill in UARPanel
         │
         ▼
2. Frontend sends RunRequest via WebSocket
         │
         ▼
3. Backend: FastAPI → SimplePlanner → Executor
         │
         ▼
4. Skill executes (trefoil_simulation / molecular / quantum)
         │
         ▼
5. Skill returns result dict with 3D data
         │
         ▼
6. binary_stream.py serializes → named chunks
         │
         ▼
7. Server emits JSON event: type="skill_complete"
         │
         ▼
8. Server emits binary frames (best-effort)
         │
         ▼
9. Frontend: UARPanel parses event → sets state
         │
         ▼
10. TrefoilKnotVisualizer receives data → renders via R3F
         │
         ▼
11. User interacts: sliders → param change → rerun skill
```

---

## 6. Capability Matrix

| Feature | Trefoil | Molecular | Quantum | Graph | Metrics |
|---|---|---|---|---|---|
| **3D rendering** | ✅ R3F | ❌ (backend only) | ❌ (backend only) | ❌ | ❌ |
| **2D rendering** | ❌ | ❌ | ❌ | ✅ ReactFlow | ✅ CSS |
| **Animation** | ✅ Keyframes 30fps | ❌ | ❌ | ❌ | ❌ |
| **PNG export** | ✅ Canvas | ❌ | ❌ | ✅ html-to-image | ❌ |
| **Interactive controls** | ✅ Sliders | ❌ | ❌ | ✅ Drag/zoom | ❌ |
| **Binary streaming** | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Auto-centering** | ❌ | ✅ | ✅ | ✅ | N/A |
| **Equilibrium detection** | ✅ | ❌ | ❌ | N/A | N/A |

---

## 7. Gaps & Future Enhancements

### 7.1 Frontend Visualizers Needed

| Skill | Missing | Priority |
|---|---|---|
| `molecular_visualization` | React Three Fiber molecule renderer (atoms as spheres, bonds as cylinders) | **High** |
| `quantum_circuit_visualization` | R3F circuit renderer (qubit tracks, gate meshes, connection lines) | **High** |
| `data_viz_3d` | PyVista → frontend bridge (mesh loading, VTK parsing) | Medium |

### 7.2 Infrastructure Gaps

| Gap | Impact | Suggested Approach |
|---|---|---|
| **No frontend binary decoder** | Binary frames from WS unused | Add `BinaryStreamDecoder` class in TypeScript |
| **GPU compute** | Large simulations CPU-bound | WebGPU compute shaders for point generation; or WASM + Web Workers |
| **No cosmology skill** | Missing from user's request list | Add `cosmology_visualization` skill (N-body, galaxy distribution) |
| **PNG export only for trefoil** | Graph exports, but molecular/quantum have no renderer | Build renderers first, then add export |
| **No SMILES parser** | Molecular skill uses hardcoded presets only | Integrate RDKit or Open Babel for arbitrary molecules |

### 7.3 Performance Optimizations

| Optimization | Target | Method |
|---|---|---|
| **Instanced rendering** | Trefoil core points | `THREE.InstancedMesh` instead of `THREE.Points` |
| **LOD (Level of Detail)** | Large molecular structures | Reduce `TubeGeometry` segments at distance |
| **Web Workers** | Keyframe computation | Offload SLERP to worker thread |
| **SharedArrayBuffer** | Binary streaming | Zero-copy transfer from WS to GPU buffer |

---

## 8. File Inventory

### Frontend
```
apps/web/src/components/
├── TrefoilKnotVisualizer.tsx          # 3D trefoil R3F renderer
├── TrefoilKnotVisualizer.module.css   # Styles
├── GraphVisualizer.tsx                 # 2D ReactFlow graph
├── GraphVisualizer.module.css
├── MetricsDashboard.tsx                # Performance metrics
├── MetricsDashboard.module.css
├── UARPanel.tsx                        # Main orchestration
├── UARPanel.module.css
├── SkillGuide.tsx
├── FilePicker.tsx
└── RecipeTimeline.tsx
```

### Backend
```
uar/skills/
├── trefoil_simulation.py               # Quaternion trefoil knots
├── molecular_visualization.py          # 3D molecular structures
└── quantum_circuit_visualization.py    # 3D quantum circuits

uar/core/
└── binary_stream.py                    # WS binary serialization

uar/api/
└── server.py                           # WS binary streaming integration
```

---

## 9. Validation Status

| Check | Command | Result |
|---|---|---|
| Unit tests | `pytest tests/ -q` | 415 passed, 37 skipped |
| Python lint | `ruff check uar/skills/*.py uar/core/binary_stream.py uar/api/server.py` | All passed |
| TypeScript | `npx tsc --noEmit` | 0 errors |
| Build | `npm run build` | ✅ 1.36MB JS |

---

*End of review. Next recommended action: build frontend React Three Fiber renderers for `molecular_visualization` and `quantum_circuit_visualization` to unlock full 3D pipeline.*
