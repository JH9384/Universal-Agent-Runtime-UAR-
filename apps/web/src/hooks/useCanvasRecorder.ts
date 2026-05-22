import { useRef, useCallback, useState } from 'react'

export interface RecorderState {
  isRecording: boolean
  recordedSeconds: number
}

interface UseCanvasRecorderReturn {
  startRecording: () => void
  stopRecording: () => void
  state: RecorderState
  error: string | null
}

/**
 * Record a WebGL/HTML5 canvas element as a WebM video using
 * canvas.captureStream() + MediaRecorder.
 *
 * @param canvasRef   Mutable ref to the canvas element (or null before mount).
 * @param fps         Target frame rate for the capture stream.
 * @param mimeType    Preferred MIME type (falls back to browser default).
 *
 * Usage (inside a component that owns the canvas):
 *   const canvasRef = useRef<HTMLCanvasElement>(null)
 *   const { startRecording, stopRecording, state, error } = useCanvasRecorder(canvasRef, 30)
 *
 *   <button onClick={state.isRecording ? stopRecording : startRecording}>
 *     {state.isRecording ? 'Stop' : 'Record'}
 *   </button>
 */
export function useCanvasRecorder(
  canvasRef: React.MutableRefObject<HTMLCanvasElement | null>,
  fps = 30,
  mimeType = 'video/webm;codecs=vp9'
): UseCanvasRecorderReturn {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [state, setState] = useState<RecorderState>({
    isRecording: false,
    recordedSeconds: 0,
  })
  const [error, setError] = useState<string | null>(null)

  const startRecording = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) {
      setError('Canvas not ready')
      return
    }

    // Reset
    chunksRef.current = []
    setError(null)
    setState({ isRecording: true, recordedSeconds: 0 })

    // Capture stream from canvas
    let stream: MediaStream
    try {
      stream = canvas.captureStream(fps)
    } catch (e) {
      setError('captureStream failed: ' + String(e))
      setState({ isRecording: false, recordedSeconds: 0 })
      return
    }

    // Pick a supported MIME type
    const finalMimeType =
      MediaRecorder.isTypeSupported(mimeType)
        ? mimeType
        : MediaRecorder.isTypeSupported('video/webm;codecs=vp8')
          ? 'video/webm;codecs=vp8'
          : 'video/webm'

    let recorder: MediaRecorder
    try {
      recorder = new MediaRecorder(stream, { mimeType: finalMimeType })
    } catch (e) {
      setError('MediaRecorder failed: ' + String(e))
      setState({ isRecording: false, recordedSeconds: 0 })
      return
    }

    recorder.ondataavailable = (evt) => {
      if (evt.data && evt.data.size > 0) {
        chunksRef.current.push(evt.data)
      }
    }

    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: finalMimeType })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `recording-${Date.now()}.webm`
      a.click()
      URL.revokeObjectURL(url)
      chunksRef.current = []
    }

    recorder.onerror = (e) => {
      setError('Recording error: ' + String(e))
      setState((s) => ({ ...s, isRecording: false }))
    }

    mediaRecorderRef.current = recorder
    recorder.start(100) // collect 100ms chunks for smoother output

    // Tick timer
    const startTime = Date.now()
    timerRef.current = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000)
      setState({ isRecording: true, recordedSeconds: elapsed })
    }, 1000)
  }, [canvasRef, fps, mimeType])

  const stopRecording = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()
    }
    mediaRecorderRef.current = null
    setState({ isRecording: false, recordedSeconds: 0 })
  }, [])

  return { startRecording, stopRecording, state, error }
}
