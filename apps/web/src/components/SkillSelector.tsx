import styles from './UARPanel.module.css'

interface Skill {
  id: string
  label: string
  desc: string
}

interface SkillGroup {
  name: string
  icon: string
  skills: Skill[]
}

interface ExecutionOrderItem {
  id: string
  type: 'skill' | 'recipe'
  content: string
}

interface SkillSelectorProps {
  skillSearch: string
  debouncedSkillSearch: string
  onSkillSearchChange: (value: string) => void
  skillsDisplayMode: 'dropdown' | 'list'
  onToggleDisplayMode: () => void
  collapsedGroups: Record<string, boolean>
  onToggleGroup: (name: string) => void
  unifiedOrder: ExecutionOrderItem[]
  onAddSkill: (id: string) => void
  isRunning: boolean
  skillGroups: SkillGroup[]
  availableSkills: Skill[]
}

function chip(active: boolean, disabled = false): string {
  const base = styles.chip
  if (active) return `${base} ${styles.chipActive}`
  if (disabled) return `${base} ${styles.chipDisabled}`
  return base
}

export default function SkillSelector({
  skillSearch,
  debouncedSkillSearch,
  onSkillSearchChange,
  skillsDisplayMode,
  onToggleDisplayMode,
  collapsedGroups,
  onToggleGroup,
  unifiedOrder,
  onAddSkill,
  isRunning,
  skillGroups,
  availableSkills,
}: SkillSelectorProps) {
  return (
    <div className={styles.sectionWithTips}>
      <div className={styles.sectionContent}>
        <div className={styles.skillSearchWrap}>
          <input
            type="text"
            value={skillSearch}
            onChange={(e) => onSkillSearchChange(e.target.value)}
            placeholder="Search skills\u2026"
            className={styles.skillSearchInput}
            aria-label="Search skills"
          />
          {skillSearch && (
            <button
              onClick={() => onSkillSearchChange('')}
              className={styles.skillSearchClear}
              aria-label="Clear search"
            >
              \u2715
            </button>
          )}
        </div>
        <div className={styles.skillsContainer}>
          {skillsDisplayMode === 'dropdown'
            ? (() => {
                const query = debouncedSkillSearch.trim().toLowerCase()
                const groups = query
                  ? skillGroups
                      .map((g) => ({
                        ...g,
                        skills: g.skills.filter(
                          (s) =>
                            s.label.toLowerCase().includes(query) ||
                            s.desc.toLowerCase().includes(query)
                        ),
                      }))
                      .filter((g) => g.skills.length > 0)
                  : skillGroups
                return groups.map((group) => {
                  const isCollapsed = collapsedGroups[group.name]
                  return (
                    <div key={group.name} className={styles.skillGroup}>
                      <div
                        className={styles.skillGroupHeader}
                        onClick={() => onToggleGroup(group.name)}
                        onKeyDown={(ev) => {
                          if (ev.key === 'Enter' || ev.key === ' ') {
                            ev.preventDefault()
                            onToggleGroup(group.name)
                          }
                        }}
                        tabIndex={0}
                        role="button"
                        aria-expanded={!isCollapsed}
                        title={`Click to ${
                          isCollapsed ? 'expand' : 'collapse'
                        } ${group.name} skills`}
                      >
                        <span className={styles.skillGroupIcon}>
                          {group.icon}
                        </span>
                        <span className={styles.skillGroupName}>
                          {group.name}
                        </span>
                        <span className={styles.collapseIcon}>
                          {isCollapsed ? '\u25B6' : '\u25BC'}
                        </span>
                      </div>
                      {!isCollapsed && (
                        <div className={styles.skillGroupSkills}>
                          {group.skills.map((s) => {
                            const count = unifiedOrder.filter(
                              (i) =>
                                i.type === 'skill' &&
                                i.content === s.id
                            ).length
                            return (
                              <button
                                key={s.id}
                                onClick={() => onAddSkill(s.id)}
                                disabled={isRunning}
                                title={s.desc}
                                className={chip(
                                  count > 0,
                                  isRunning
                                )}
                              >
                                {count > 0
                                  ? `\u2713 (${count}) `
                                  : ''}
                                {s.label}
                              </button>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  )
                })
              })()
            : (
                <div className={styles.skillGroupSkills}>
                  {availableSkills.map((s) => {
                    const count = unifiedOrder.filter(
                      (i) =>
                        i.type === 'skill' && i.content === s.id
                    ).length
                    return (
                      <button
                        key={s.id}
                        onClick={() => onAddSkill(s.id)}
                        disabled={isRunning}
                        title={s.desc}
                        className={chip(count > 0, isRunning)}
                      >
                        {count > 0 ? `\u2713 (${count}) ` : ''}
                        {s.label}
                      </button>
                    )
                  })}
                </div>
              )}
        </div>
      </div>
    </div>
  )
}
