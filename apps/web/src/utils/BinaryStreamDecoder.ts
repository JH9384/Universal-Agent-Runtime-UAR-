/**
 * Decode WebSocket binary frames for visualization skills.
 *
 * The server sends binary frames with the format:
 *   name_bytes + "\x00" + payload_bytes
 *
 * Where name identifies the chunk (e.g. "knot_0", "atoms", "meta").
 */

export interface TrefoilBinaryChunks {
  knots: Float64Array[]
  core: Float64Array | null
  meta: {
    numPoints: number
    numTrefoils: number
    keyframeCount: number
    equilibrium: boolean
    expansion: number
    torsionalSync: number
    twistorStrength: number
    phaseLockStrength: number
  }
}

export interface MolecularBinaryChunks {
  atoms: Float64Array | null
  bonds: Float64Array | null
  meta: {
    atomCount: number
    bondCount: number
  }
}

export interface QuantumCircuitBinaryChunks {
  tracks: Float64Array | null
  gates: Float64Array | null
  meta: {
    qubits: number
    depth: number
    gateCount: number
  }
}

function splitFrame(data: ArrayBuffer): { name: string; payload: ArrayBuffer } {
  const view = new Uint8Array(data)
  const nullIdx = view.indexOf(0)
  if (nullIdx === -1) {
    return { name: '', payload: data }
  }
  const name = new TextDecoder().decode(view.slice(0, nullIdx))
  const payload = data.slice(nullIdx + 1)
  return { name, payload }
}

function decodeFloats(buf: ArrayBuffer): Float64Array {
  return new Float64Array(buf)
}

function decodeInts(buf: ArrayBuffer, count: number): number[] {
  const view = new DataView(buf)
  const result: number[] = []
  for (let i = 0; i < count; i++) {
    result.push(view.getInt32(i * 4, true))
  }
  return result
}

function decodeDoubles(buf: ArrayBuffer, offset: number, count: number): number[] {
  const view = new DataView(buf)
  const result: number[] = []
  for (let i = 0; i < count; i++) {
    result.push(view.getFloat64(offset + i * 8, true))
  }
  return result
}

export function decodeTrefoilBinary(data: ArrayBuffer): Partial<TrefoilBinaryChunks> {
  const { name, payload } = splitFrame(data)
  const result: Partial<TrefoilBinaryChunks> = {}

  if (name.startsWith('knot_')) {
    if (!result.knots) result.knots = []
    result.knots.push(decodeFloats(payload))
  } else if (name === 'core') {
    result.core = decodeFloats(payload)
  } else if (name === 'meta') {
    const ints = decodeInts(payload, 4)
    const doubles = decodeDoubles(payload, 16, 4)
    result.meta = {
      numPoints: ints[0] ?? 0,
      numTrefoils: ints[1] ?? 0,
      keyframeCount: ints[2] ?? 0,
      equilibrium: (ints[3] ?? 0) === 1,
      expansion: doubles[0] ?? 1.0,
      torsionalSync: doubles[1] ?? 0.0,
      twistorStrength: doubles[2] ?? 0.0,
      phaseLockStrength: doubles[3] ?? 0.0,
    }
  }

  return result
}

export function decodeMolecularBinary(data: ArrayBuffer): Partial<MolecularBinaryChunks> {
  const { name, payload } = splitFrame(data)
  const result: Partial<MolecularBinaryChunks> = {}

  if (name === 'atoms') {
    result.atoms = decodeFloats(payload)
  } else if (name === 'bonds') {
    result.bonds = decodeFloats(payload)
  } else if (name === 'meta') {
    const ints = decodeInts(payload, 2)
    result.meta = {
      atomCount: ints[0] ?? 0,
      bondCount: ints[1] ?? 0,
    }
  }

  return result
}

export function decodeQuantumCircuitBinary(
  data: ArrayBuffer,
): Partial<QuantumCircuitBinaryChunks> {
  const { name, payload } = splitFrame(data)
  const result: Partial<QuantumCircuitBinaryChunks> = {}

  if (name === 'tracks') {
    result.tracks = decodeFloats(payload)
  } else if (name === 'gates') {
    result.gates = decodeFloats(payload)
  } else if (name === 'meta') {
    const ints = decodeInts(payload, 3)
    result.meta = {
      qubits: ints[0] ?? 0,
      depth: ints[1] ?? 0,
      gateCount: ints[2] ?? 0,
    }
  }

  return result
}

export function decodeBinaryVisualization(
  data: ArrayBuffer,
  skill: string,
):
  | Partial<TrefoilBinaryChunks>
  | Partial<MolecularBinaryChunks>
  | Partial<QuantumCircuitBinaryChunks>
  | null {
  switch (skill) {
    case 'trefoil_simulation':
      return decodeTrefoilBinary(data)
    case 'molecular_visualization':
      return decodeMolecularBinary(data)
    case 'quantum_circuit_visualization':
      return decodeQuantumCircuitBinary(data)
    default:
      return null
  }
}
