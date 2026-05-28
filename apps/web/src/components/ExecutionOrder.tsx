import styles from './UARPanel.module.css'

const RECIPE_ICON = '🍳'
const REMOVE_ICON = '✕'

export interface ExecutionOrderItem {
  id: string
  type: 'skill' | 'recipe'
  content: string
}

interface Recipe {
  id: string
  label: string
}

interface ExecutionOrderProps {
  items: ExecutionOrderItem[]
  recipes: Recipe[]
  isRunning: boolean
  onReorder: (fromId: string, toIndex: number) => void
  onDuplicate: (index: number) => void
  onRemove: (index: number) => void
}

function getColorClass(id: string): string {
  const hash = id.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
  return `color-${hash % 10}`
}

function getLabel(item: ExecutionOrderItem, recipes: Recipe[]): string {
  if (item.type === 'skill') return item.content
  return recipes.find((r) => r.id === item.content)?.label ?? item.content
}

function handleDragStart(e: React.DragEvent, id: string) {
  e.dataTransfer.setData('text/uar-order', id)
  e.dataTransfer.effectAllowed = 'move'
}

function handleDrop(
  e: React.DragEvent,
  index: number,
  onReorder: (fromId: string, toIndex: number) => void
) {
  e.preventDefault()
  if (!Array.from(e.dataTransfer.types).includes('text/uar-order')) return
  const fromId = e.dataTransfer.getData('text/uar-order')
  onReorder(fromId, index)
}

export default function ExecutionOrder({
  items,
  recipes,
  isRunning,
  onReorder,
  onDuplicate,
  onRemove,
}: ExecutionOrderProps) {
  if (items.length === 0) {
    return (
      <span className={styles.orderEmpty}>
        No skills or recipes selected — click above to build your pipeline
      </span>
    )
  }

  return (
    <div className={styles.orderChips}>
      {items.map((item, index) => {
        const label = getLabel(item, recipes)
        const colorClass = getColorClass(item.id)
        const ariaLabel = `${item.type === 'recipe' ? 'Recipe' : 'Skill'}: ${label} (position ${index + 1})`

        return (
          <div
            key={item.id}
            className={`${styles.orderChip} ${styles[colorClass]}`}
            draggable={!isRunning}
            tabIndex={0}
            role="button"
            aria-label={ariaLabel}
            onDragStart={(e) => handleDragStart(e, item.id)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => handleDrop(e, index, onReorder)}
            onKeyDown={(e) => {
              if (isRunning) return
              if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                e.preventDefault()
                if (index > 0) onReorder(item.id, index - 1)
              } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                e.preventDefault()
                if (index < items.length - 1) onReorder(item.id, index + 1)
              } else if (e.key === 'Delete' || e.key === 'Backspace') {
                e.preventDefault()
                onRemove(index)
              }
            }}
          >
            {item.type === 'recipe' ? `${RECIPE_ICON} ` : ''}
            {label}
            <button
              className={styles.orderChipAction}
              disabled={isRunning}
              title={`Duplicate ${label}`}
              aria-label={`Duplicate ${label}`}
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                onDuplicate(index)
              }}
            >
              +
            </button>
            <button
              className={styles.orderChipAction}
              disabled={isRunning}
              title={`Remove ${label}`}
              aria-label={`Remove ${label}`}
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                onRemove(index)
              }}
            >
              {REMOVE_ICON}
            </button>
          </div>
        )
      })}
    </div>
  )
}
