import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ExecutionOrder, { type ExecutionOrderItem } from '../ExecutionOrder'

const RECIPES = [
  { id: 'recipe-a', label: 'Recipe A' },
  { id: 'recipe-b', label: 'Recipe B' },
]

function renderExecutionOrder(
  items: ExecutionOrderItem[],
  overrides: Partial<Parameters<typeof ExecutionOrder>[0]> = {}
) {
  const props = {
    items,
    recipes: RECIPES,
    isRunning: false,
    onReorder: vi.fn(),
    onDuplicate: vi.fn(),
    onRemove: vi.fn(),
    ...overrides,
  }
  return render(<ExecutionOrder {...props} />)
}

describe('ExecutionOrder', () => {
  it('renders empty state when no items', () => {
    renderExecutionOrder([])
    expect(
      screen.getByText(/No skills or recipes selected/)
    ).toBeInTheDocument()
  })

  it('renders skill chips with labels', () => {
    const items: ExecutionOrderItem[] = [
      { id: 's1', type: 'skill', content: 'doc_ingest' },
      { id: 's2', type: 'skill', content: 'sum_review' },
    ]
    renderExecutionOrder(items)

    expect(screen.getByText('doc_ingest')).toBeInTheDocument()
    expect(screen.getByText('sum_review')).toBeInTheDocument()
  })

  it('renders recipe chips with resolved labels', () => {
    const items: ExecutionOrderItem[] = [
      { id: 'r1', type: 'recipe', content: 'recipe-a' },
    ]
    renderExecutionOrder(items)

    expect(screen.getByText('🍳 Recipe A')).toBeInTheDocument()
  })

  it('falls back to raw content when recipe label missing', () => {
    const items: ExecutionOrderItem[] = [
      { id: 'r1', type: 'recipe', content: 'unknown-recipe' },
    ]
    renderExecutionOrder(items)

    expect(screen.getByText('🍳 unknown-recipe')).toBeInTheDocument()
  })

  it('assigns aria-label with position info', () => {
    const items: ExecutionOrderItem[] = [
      { id: 's1', type: 'skill', content: 'doc_ingest' },
    ]
    renderExecutionOrder(items)

    expect(
      screen.getByLabelText('Skill: doc_ingest (position 1)')
    ).toBeInTheDocument()
  })

  it('calls onDuplicate when duplicate button clicked', () => {
    const onDuplicate = vi.fn()
    const items: ExecutionOrderItem[] = [
      { id: 's1', type: 'skill', content: 'doc_ingest' },
    ]
    renderExecutionOrder(items, { onDuplicate })

    fireEvent.click(screen.getByLabelText('Duplicate doc_ingest'))
    expect(onDuplicate).toHaveBeenCalledWith(0)
  })

  it('calls onRemove when remove button clicked', () => {
    const onRemove = vi.fn()
    const items: ExecutionOrderItem[] = [
      { id: 's1', type: 'skill', content: 'doc_ingest' },
    ]
    renderExecutionOrder(items, { onRemove })

    fireEvent.click(screen.getByLabelText('Remove doc_ingest'))
    expect(onRemove).toHaveBeenCalledWith(0)
  })

  it('calls onReorder on drop', () => {
    const onReorder = vi.fn()
    const items: ExecutionOrderItem[] = [
      { id: 's1', type: 'skill', content: 'a' },
      { id: 's2', type: 'skill', content: 'b' },
    ]
    renderExecutionOrder(items, { onReorder })

    const source = screen.getByLabelText('Skill: a (position 1)')
    const target = screen.getByLabelText('Skill: b (position 2)')

    // Simulate drag start
    fireEvent.dragStart(source, {
      dataTransfer: {
        setData: vi.fn(),
        effectAllowed: '',
      },
    })

    // Simulate drop with proper dataTransfer types
    const dataTransfer = {
      types: ['text/uar-order'],
      getData: vi.fn().mockReturnValue('s1'),
    }
    fireEvent.drop(target, { dataTransfer })

    expect(onReorder).toHaveBeenCalledWith('s1', 1)
  })

  it('disables buttons when isRunning is true', () => {
    const items: ExecutionOrderItem[] = [
      { id: 's1', type: 'skill', content: 'doc_ingest' },
    ]
    renderExecutionOrder(items, { isRunning: true })

    const dup = screen.getByLabelText('Duplicate doc_ingest')
    const rem = screen.getByLabelText('Remove doc_ingest')

    expect(dup).toBeDisabled()
    expect(rem).toBeDisabled()
  })

  it('makes chips draggable only when not running', () => {
    const items: ExecutionOrderItem[] = [
      { id: 's1', type: 'skill', content: 'doc_ingest' },
    ]

    const { rerender } = renderExecutionOrder(items, { isRunning: false })
    expect(screen.getByLabelText('Skill: doc_ingest (position 1)')).toHaveAttribute('draggable', 'true')

    rerender(<ExecutionOrder items={items} recipes={RECIPES} isRunning={true} onReorder={vi.fn()} onDuplicate={vi.fn()} onRemove={vi.fn()} />)
    expect(screen.getByLabelText('Skill: doc_ingest (position 1)')).toHaveAttribute('draggable', 'false')
  })
})
