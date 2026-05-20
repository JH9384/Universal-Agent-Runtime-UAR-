// Improved ID generation with collision prevention. Resets on page
// reload, which is acceptable for the UI's transient unified-order
// items.
let idCounter = 0
const componentInstanceId = Math.random().toString(36).substring(2, 9)

function generate(): string {
  try {
    return crypto.randomUUID()
  } catch {
    // Fallback: timestamp + counter + random + module instance for
    // strong collision resistance across reloads
    const timestamp = Date.now().toString(36)
    const counter = (idCounter++).toString(36)
    const random = Math.random().toString(36).substring(2, 9)
    return `${timestamp}-${counter}-${random}-${componentInstanceId}`
  }
}

/**
 * Generate a unique string id, optionally avoiding collisions with an
 * existing set. Falls back to timestamped randomness if `crypto.randomUUID`
 * is unavailable.
 */
export function generateUniqueId(existingIds?: Set<string>): string {
  let id = generate()
  if (!existingIds) return id

  let attempts = 0
  const maxAttempts = 100
  while (existingIds.has(id) && attempts < maxAttempts) {
    id = generate()
    attempts++
  }
  if (attempts >= maxAttempts) {
    // Last-resort: full timestamp + extra entropy
    return `${Date.now()}-${Math.random()
      .toString(36)
      .substring(2, 15)}-${componentInstanceId}`
  }
  return id
}
