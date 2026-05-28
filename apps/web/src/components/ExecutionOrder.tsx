import { generateUniqueId } from '../utils/idGenerator'
import styles from './UARPanel.module.css'

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
  onClear: () => void
}

export default function ExecutionOrder({
  items,
  recipes,
  isRunning,
  onReorder,
  onDuplicate,
  onRemove,
  onClear,
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
        const hash = item.id
          .split('')
          .reduce((acc, char) => acc + char.charCodeAt(0), 0)
        const colorClass = `color-${hash % 10}`
        const label =
          item.type === 'skill'
            ? item.content
            : recipes.find((r) => r.id === item.content)?.label ||
              item.content
        return (
          <div
            key={item.id}
            className={`${styles.orderChip} ${styles[colorClass]}`}
            draggable={!isRunning}
            aria-label={`${item.type === 'recipe' ? 'Recipe' : 'Skill'}: ${label} (position ${index + 1})`}
            onDragStart={(e) => {
              e.dataTransfer.setData('text/uar-order', item.id)
              e.dataTransfer.effectAllowed = 'move'
            }}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault()
              if (
                !Array.from(e.dataTransfer.types).includes(
                  'text/uar-order'
                )
              )
                return
              const fromId = e.dataTransfer.getData('text/uar-order')
              onReorder(fromId, index)
            }}
          >
            {item.type === 'recipe' ? '\uD83C\uDF73 ' : ''}
            {label}
            <button
              onClick={(e) => {
                e.stopPropagation()
                onDuplicate(index)
              }}
              className={styles.orderChipAction}
              disabled={isRunning}
              title={`Duplicate ${label}`}
              aria-label={`Duplicate ${label}`}
            >
              +
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation()
                onRemove(index)
              }}
              className={styles.orderChipAction}
              disabled={isRunning}
              title={`Remove ${label}`}
              aria-label={`Remove ${label}`}
            >
              \u2715
            </button>
          </div>
        )
      })}
    </div>
  )
}
