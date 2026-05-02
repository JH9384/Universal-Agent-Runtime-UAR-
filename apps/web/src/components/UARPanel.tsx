import { useState } from 'react'

export function UARPanel() {
  const [goal, setGoal] = useState('')
  const [output, setOutput] = useState<any>(null)

  const runGoal = async () => {
    // placeholder: this will call backend later
    setOutput({ status: 'stub', goal })
  }

  return (
    <div style={{ padding: 12, border: '1px solid #333' }}>
      <h3>UAR Control Panel</h3>
      <input
        value={goal}
        onChange={(e) => setGoal(e.target.value)}
        placeholder="Enter goal"
      />
      <button onClick={runGoal}>Run</button>

      <pre>{JSON.stringify(output, null, 2)}</pre>
    </div>
  )
}
