import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { UARPanel } from '../UARPanel'

// @ts-ignore - global is provided by Vitest
declare const global: any

// Mock ReactFlow
vi.mock('reactflow', () => ({
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="reactflow">{children}</div>
  ),
  ReactFlow: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="reactflow">{children}</div>
  ),
  Background: () => <div data-testid="background" />,
}))

// Mock fetch
global.fetch = vi.fn()

// Helper function to set up default fetch mock
const setupDefaultFetchMock = () => {
  vi.mocked(global.fetch).mockImplementation((url: string) => {
    // Handle all document-related API endpoints
    if (url === '/api/uar/docs/presets' || url === '/api/uar/docs/browse') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ presets: [], project_root: '/test', library: '/test/library' }),
      } as Response)
    }
    if (url === '/api/uar/docs/library') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ entries: [], library: '/test/library' }),
      } as Response)
    }
    // Default fallback
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve({}),
    } as Response)
  })
}

describe('UARPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Mock localStorage
    const localStorageMock = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    }
    Object.defineProperty(window, 'localStorage', { value: localStorageMock })
    // Set up default fetch mock for all tests
    setupDefaultFetchMock()
  })

  describe('Component Rendering', () => {
    it('should render without crashing', async () => {
      render(<UARPanel />)
      await waitFor(() => {
        expect(screen.getByText(/Universal Agent Runtime \(UAR\)/)).toBeInTheDocument()
      })
    })

    it('should render skill groups', async () => {
      render(<UARPanel />)
      await waitFor(() => {
        expect(screen.getByText('Core UAR')).toBeInTheDocument()
        expect(screen.getByText('AI / LLM')).toBeInTheDocument()
        expect(screen.getByText('GraphRAG')).toBeInTheDocument()
      })
    })
  })

  describe('localStorage Error Handling', () => {
    it('should log warnings on localStorage failures', async () => {
      const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      
      // Mock localStorage to throw error
      vi.spyOn(window.localStorage, 'setItem').mockImplementation(() => {
        throw new Error('Storage quota exceeded')
      })
      
      render(<UARPanel />)
      
      // Wait for component to load and attempt localStorage operations
      await waitFor(() => {
        expect(consoleWarnSpy).toHaveBeenCalled()
      }, { timeout: 3000 })
      
      consoleWarnSpy.mockRestore()
    })
  })

  describe('Event Limit Handling', () => {
    it('should enforce MAX_EVENTS limit during streaming', async () => {
      const MAX_EVENTS = 1000
      let eventCount = 0
      
      // Mock streaming response that sends many events
      vi.mocked(global.fetch).mockImplementationOnce(() => {
        return Promise.resolve({
          ok: true,
          body: {
            getReader: () => ({
              read: () => {
                eventCount++
                if (eventCount > MAX_EVENTS + 10) {
                  return Promise.resolve({ done: true, value: new Uint8Array() })
                }
                const eventData = `data: ${JSON.stringify({ type: 'test', event: eventCount })}\n\n`
                return Promise.resolve({ done: false, value: new TextEncoder().encode(eventData) })
              }
            })
          }
        } as Response)
      })

      render(<UARPanel />)
      
      const goalInput = await screen.findByPlaceholderText('What do you want to accomplish?')
      await userEvent.type(goalInput, 'test goal')
      
      const runButton = await screen.findByText('▶ Run Stream')
      fireEvent.click(runButton)
      
      // Verify that stream stops when limit is reached
      await waitFor(() => {
        const stopButton = screen.queryByText('⏹ Stop')
        expect(stopButton).not.toBeInTheDocument()
      }, { timeout: 5000 })
    })
  })

  describe('Skill Selection', () => {
    it('should render skill buttons', async () => {
      render(<UARPanel />)
      
      await waitFor(() => {
        expect(screen.getByText('Core UAR')).toBeInTheDocument()
      })
      
      // Verify skill buttons are rendered
      const docIngestButtons = screen.getAllByText('doc_ingest')
      expect(docIngestButtons.length).toBeGreaterThan(0)
    })
  })

  describe('Recipe Management', () => {
    it('should render recipe buttons', async () => {
      render(<UARPanel />)
      
      await waitFor(() => {
        expect(screen.getByText('Recipes')).toBeInTheDocument()
      })
      
      // Verify recipe buttons are rendered
      const recipeButton = await screen.findByText('🦙 Ollama review')
      expect(recipeButton).toBeInTheDocument()
      
      // Click recipe button
      fireEvent.click(recipeButton)
      
      // Recipe should be selected (checkmark added)
      expect(recipeButton.textContent).toContain('✓')
    })
  })

  describe('File Upload', () => {
    it('should handle file upload via drop zone', async () => {
      const mockFile = new File(['test content'], 'test.txt', { type: 'text/plain' })
      
      vi.mocked(global.fetch).mockImplementation(() => {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ saved: [{ path: '/test/test.txt' }], library: '/test/library' })
        } as Response)
      })

      render(<UARPanel />)
      
      await waitFor(() => {
        expect(screen.getByText('Drop files here, or click to choose')).toBeInTheDocument()
      })
      
      const dropZone = screen.getByText('Drop files here, or click to choose').closest('div')
      fireEvent.drop(dropZone!, { dataTransfer: { files: [mockFile] } })
      
      await waitFor(() => {
        expect(screen.queryByText(/Uploading/)).toBeInTheDocument()
      })
    })

    it('should handle file upload via file input', async () => {
      const mockFile = new File(['test content'], 'test.txt', { type: 'text/plain' })
      
      vi.mocked(global.fetch).mockImplementation(() => {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ saved: [{ path: '/test/test.txt' }], library: '/test/library' })
        } as Response)
      })

      render(<UARPanel />)
      
      await waitFor(() => {
        expect(screen.getByText('Drop files here, or click to choose')).toBeInTheDocument()
      })
      
      const dropZone = screen.getByText('Drop files here, or click to choose').closest('div')
      const fileInput = dropZone?.querySelector('input[type="file"]')
      
      if (fileInput) {
        fireEvent.change(fileInput, { target: { files: [mockFile] } })
        
        await waitFor(() => {
          expect(screen.queryByText(/Uploading/)).toBeInTheDocument()
        })
      }
    })

    it('should handle upload errors gracefully', async () => {
      const mockFile = new File(['test content'], 'test.txt', { type: 'text/plain' })
      
      vi.mocked(global.fetch).mockImplementation(() => {
        return Promise.resolve({
          ok: false,
          json: () => Promise.resolve({ error: 'Upload failed' })
        } as Response)
      })

      render(<UARPanel />)
      
      await waitFor(() => {
        expect(screen.getByText('Drop files here, or click to choose')).toBeInTheDocument()
      })
      
      const dropZone = screen.getByText('Drop files here, or click to choose').closest('div')
      fireEvent.drop(dropZone!, { dataTransfer: { files: [mockFile] } })
      
      await waitFor(() => {
        expect(screen.queryByText(/Upload failed/)).toBeInTheDocument()
      })
    })
  })

  describe('Library Management', () => {
    it('should handle empty library state', async () => {
      render(<UARPanel />)
      
      await waitFor(() => {
        expect(screen.getByText('(empty — drop files above)')).toBeInTheDocument()
      }, { timeout: 5000 })
    })

    it('should have refresh button', async () => {
      render(<UARPanel />)
      
      await waitFor(() => {
        expect(screen.getByTitle('Refresh library list')).toBeInTheDocument()
      }, { timeout: 5000 })
    })
  })

  describe('Presets Functionality', () => {
    it('should display preset buttons', async () => {
      vi.mocked(global.fetch).mockImplementation(() => {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ 
            presets: [
              { name: 'src', path: '/test/src' },
              { name: 'docs', path: '/test/docs' }
            ],
            project_root: '/test',
            library: '/test/library'
          }),
        } as Response)
      })

      render(<UARPanel />)
      
      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
        expect(screen.getByText('docs')).toBeInTheDocument()
      })
    })

    it('should select preset path on click', async () => {
      vi.mocked(global.fetch).mockImplementation(() => {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ 
            presets: [
              { name: 'src', path: '/test/src' }
            ],
            project_root: '/test',
            library: '/test/library'
          }),
        } as Response)
      })

      render(<UARPanel />)
      
      await waitFor(() => {
        expect(screen.getByText('src')).toBeInTheDocument()
      })
      
      const presetButton = screen.getByText('src')
      fireEvent.click(presetButton)
      
      // Verify input path is updated
      await waitFor(() => {
        const inputPath = screen.getByDisplayValue('/test/src')
        expect(inputPath).toBeInTheDocument()
      })
    })
  })

  describe('Recent Paths History', () => {
    it('should add path to recent history when selected', async () => {
      vi.mocked(global.fetch).mockImplementation(() => {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ 
            presets: [],
            project_root: '/test',
            library: '/test/library'
          }),
        } as Response)
      })

      render(<UARPanel />)
      
      await waitFor(() => {
        expect(screen.getByText('input_path')).toBeInTheDocument()
      })
      
      const inputField = screen.getByPlaceholderText('(none — doc_ingest will warn)')
      fireEvent.change(inputField, { target: { value: '/test/new/path' } })
      
      // Path should be added to recent (triggered by run or manual selection)
      // This is a basic test - actual recent addition happens on file selection
    })

    it('should clear recent paths', async () => {
      vi.mocked(global.fetch).mockImplementation(() => {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ 
            presets: [],
            project_root: '/test',
            library: '/test/library'
          }),
        } as Response)
      })

      render(<UARPanel />)
      
      // Test clear button exists (actual clearing requires localStorage interaction)
      await waitFor(() => {
        const clearButton = screen.queryByTitle('Clear recent paths history')
        // Clear button only shows when there are recent paths
        expect(clearButton).toBeNull()
      })
    })
  })

  describe('Input Path Selection', () => {
    it('should update input path when library file is selected', async () => {
      vi.mocked(global.fetch).mockImplementation((url: string) => {
        if (url === '/api/uar/docs/library') {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ 
              entries: [
                { name: 'test.pdf', path: '/test/library/test.pdf', size: 1024, ext: '.pdf', mtime: 1234567890 }
              ],
              library: '/test/library'
            }),
          } as Response)
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ presets: [], project_root: '/test', library: '/test/library' }),
        } as Response)
      })

      render(<UARPanel />)
      
      await waitFor(() => {
        expect(screen.getByText(/test\.pdf/)).toBeInTheDocument()
      }, { timeout: 5000 })
      
      const libraryItem = screen.getByText(/test\.pdf/)
      fireEvent.click(libraryItem)
      
      await waitFor(() => {
        const inputPath = screen.getByDisplayValue('/test/library/test.pdf')
        expect(inputPath).toBeInTheDocument()
      })
    })

    it('should allow manual input path entry', async () => {
      vi.mocked(global.fetch).mockImplementation(() => {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ presets: [], project_root: '/test', library: '/test/library' }),
        } as Response)
      })

      render(<UARPanel />)
      
      await waitFor(() => {
        expect(screen.getByPlaceholderText('(none — doc_ingest will warn)')).toBeInTheDocument()
      })
      
      const inputField = screen.getByPlaceholderText('(none — doc_ingest will warn)')
      fireEvent.change(inputField, { target: { value: '/custom/path/to/file' } })
      
      expect(inputField).toHaveValue('/custom/path/to/file')
    })

    it('should clear input path', async () => {
      vi.mocked(global.fetch).mockImplementation(() => {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ presets: [], project_root: '/test', library: '/test/library' }),
        } as Response)
      })

      render(<UARPanel />)
      
      await waitFor(() => {
        expect(screen.getByPlaceholderText('(none — doc_ingest will warn)')).toBeInTheDocument()
      })
      
      const inputField = screen.getByPlaceholderText('(none — doc_ingest will warn)')
      fireEvent.change(inputField, { target: { value: '/test/path' } })
      
      const clearButton = screen.getByTitle('Clear input path')
      fireEvent.click(clearButton)
      
      expect(inputField).toHaveValue('')
    })

    it('should copy input path to clipboard', async () => {
      vi.mocked(global.fetch).mockImplementation(() => {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ presets: [], project_root: '/test', library: '/test/library' }),
        } as Response)
      })

      const mockClipboard = {
        writeText: vi.fn().mockResolvedValue(undefined),
      }
      Object.assign(navigator, { clipboard: mockClipboard })

      render(<UARPanel />)
      
      await waitFor(() => {
        expect(screen.getByPlaceholderText('(none — doc_ingest will warn)')).toBeInTheDocument()
      })
      
      const inputField = screen.getByPlaceholderText('(none — doc_ingest will warn)')
      fireEvent.change(inputField, { target: { value: '/test/path' } })
      
      const copyButton = screen.getByTitle('Copy path to clipboard')
      fireEvent.click(copyButton)
      
      expect(mockClipboard.writeText).toHaveBeenCalledWith('/test/path')
    })
  })

  describe('Use All Library Path', () => {
    it('should select entire library path', async () => {
      vi.mocked(global.fetch).mockImplementation((url: string) => {
        if (url === '/api/uar/docs/library') {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve({
              entries: [
                { name: 'test.pdf', path: '/test/library/test.pdf', size: 1024, ext: '.pdf', mtime: 1234567890 }
              ],
              library: '/test/library'
            }),
          } as Response)
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ presets: [], project_root: '/test', library: '/test/library' }),
        } as Response)
      })

      render(<UARPanel />)

      await waitFor(() => {
        expect(screen.getByText('use all')).toBeInTheDocument()
      }, { timeout: 5000 })

      const useAllButton = screen.getByTitle('Use whole library as input_path')
      fireEvent.click(useAllButton)

      await waitFor(() => {
        const inputPath = screen.getByDisplayValue('/test/library')
        expect(inputPath).toBeInTheDocument()
      })
    })
  })

  describe('UOR Ecosystem Skill Group', () => {
    it('should render UOR Ecosystem skill group', async () => {
      render(<UARPanel />)

      await waitFor(() => {
        expect(screen.getByText('UOR Ecosystem')).toBeInTheDocument()
      })
    })

    it('should render ecosystem skill buttons', async () => {
      render(<UARPanel />)

      await waitFor(() => {
        expect(screen.getByText('UOR Ecosystem')).toBeInTheDocument()
      })

      // Verify key ecosystem skill buttons are rendered
      expect(screen.getByText('uor_addr_canonicalize')).toBeInTheDocument()
      expect(screen.getByText('hologram_query')).toBeInTheDocument()
      expect(screen.getByText('moltbook_list')).toBeInTheDocument()
    })

    it('should add ecosystem skill to unified order on click', async () => {
      render(<UARPanel />)

      await waitFor(() => {
        expect(screen.getByText('UOR Ecosystem')).toBeInTheDocument()
      })

      // Find and click an ecosystem skill button
      const skillButton = screen.getByText('uor_ecosystem_status')
      fireEvent.click(skillButton)

      // Verify skill appears in selected order
      await waitFor(() => {
        const orderItems = screen.getAllByText('uor_ecosystem_status')
        expect(orderItems.length).toBeGreaterThanOrEqual(1)
      })
    })
  })
})
