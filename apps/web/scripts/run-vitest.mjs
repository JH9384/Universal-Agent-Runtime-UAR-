import { spawn } from 'node:child_process'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const args = process.argv.slice(2)
const [major, minor] = process.versions.node.split('.').map(Number)
const supportsLocalStorageFile = major > 22 || (major === 22 && minor >= 4)
const localStorageFlag = `--localstorage-file=${join(
  tmpdir(),
  'uar-vitest-localstorage.json'
)}`

const env = { ...process.env }
if (
  supportsLocalStorageFile &&
  !String(env.NODE_OPTIONS || '').includes('--localstorage-file')
) {
  env.NODE_OPTIONS = [env.NODE_OPTIONS, localStorageFlag]
    .filter(Boolean)
    .join(' ')
}

const child = spawn('vitest', args, {
  env,
  shell: process.platform === 'win32',
  stdio: 'inherit',
})

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal)
    return
  }
  process.exit(code ?? 1)
})
