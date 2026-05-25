import { readdir, stat } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const distAssets = fileURLToPath(new URL('../dist/assets/', import.meta.url))

const kib = (bytes) => bytes / 1024

const budgets = [
  { match: /^index-.*\.js$/, limitKiB: 230 },
  { match: /^vendor-react-.*\.js$/, limitKiB: 330 },
  { match: /^vendor-three-core-.*\.js$/, limitKiB: 800 },
  { match: /^vendor-three-fiber-.*\.js$/, limitKiB: 180 },
  { match: /^vendor-three-drei-.*\.js$/, limitKiB: 20 },
  { match: /^useCanvasRecorder-.*\.js$/, limitKiB: 8 },
]

const files = await readdir(distAssets)
const failures = []

for (const file of files) {
  if (!file.endsWith('.js')) continue
  const { size } = await stat(join(distAssets, file))
  const budget = budgets.find(({ match }) => match.test(file))
  if (budget && kib(size) > budget.limitKiB) {
    failures.push(
      `${file}: ${kib(size).toFixed(1)} KiB exceeds ${budget.limitKiB} KiB`
    )
  }
}

if (failures.length > 0) {
  console.error('Bundle budget exceeded:')
  for (const failure of failures) {
    console.error(`- ${failure}`)
  }
  process.exit(1)
}

console.log('Bundle budget OK')
