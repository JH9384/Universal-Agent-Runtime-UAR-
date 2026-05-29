import styles from './UARPanel.module.css'
import { type ExecutionOrderItem } from './ExecutionOrder'

const CLEAR_ICON = '✕'
const COLLAPSED_ICON = '▶'
const EXPANDED_ICON = '▼'
const CHECK_ICON = '✓'

const BADGE_EMOJI: Record<string, string> = {
  real: '🟢',
  stub: '🔴',
  cosplay: '🟡',
}

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
  badges: Record<string, 'real' | 'stub' | 'cosplay'>
  stubDeps: Record<string, string>
}

function chip(active: boolean, disabled = false): string {
  const base = styles.chip
  if (active) return `${base} ${styles.chipActive}`
  if (disabled) return `${base} ${styles.chipDisabled}`
  return base
}

function getSkillCount(unifiedOrder: ExecutionOrderItem[], skillId: string): number {
  return unifiedOrder.filter(
    (i) => i.type === 'skill' && i.content === skillId
  ).length
}

function getCheckedLabel(count: number, label: string): string {
  if (count > 0) return `${CHECK_ICON} (${count}) ${label}`
  return label
}

function buildTitle(
  badge: 'real' | 'stub' | 'cosplay' | undefined,
  dep: string,
  desc: string
): string {
  if (badge === 'stub') {
    const install = dep
      ? `Install ${dep} to enable.`
      : 'Not yet implemented.'
    return `${install} ${desc}`
  }
  if (badge === 'cosplay') {
    return `${desc} (UAR-native)`
  }
  return desc
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
  badges,
  stubDeps,
}: SkillSelectorProps) {
  return (
    <div className={styles.sectionWithTips}>
      <div className={styles.sectionContent}>
        <div className={styles.skillSearchWrap}>
          <input
            type="text"
            value={skillSearch}
            onChange={(e) => onSkillSearchChange(e.target.value)}
            placeholder="Search skills…"
            className={styles.skillSearchInput}
            aria-label="Search skills"
          />
          {skillSearch && (
            <button
              onClick={() => onSkillSearchChange('')}
              className={styles.skillSearchClear}
              aria-label="Clear search"
            >
              {CLEAR_ICON}
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
                          {isCollapsed ? COLLAPSED_ICON : EXPANDED_ICON}
                        </span>
                      </div>
                      {!isCollapsed && (
                        <div className={styles.skillGroupSkills}>
                          {group.skills.map((s) => {
                            const count = getSkillCount(unifiedOrder, s.id)
                            const badge = badges[s.id]
                            const isStub = badge === 'stub'
                            const emoji = BADGE_EMOJI[badge ?? 'real']
                            const title = buildTitle(
                              badge,
                              stubDeps[s.id] ?? '',
                              s.desc
                            )
                            return (
                              <button
                                key={s.id}
                                onClick={() => onAddSkill(s.id)}
                                disabled={isRunning || isStub}
                                title={title}
                                className={chip(
                                  count > 0,
                                  isRunning || isStub
                                )}
                              >
                                <span
                                  className={styles.skillBadge}
                                  aria-label={`${badge ?? 'real'} skill`}
                                >
                                  {emoji}
                                </span>
                                {getCheckedLabel(count, s.label)}
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
                    const count = getSkillCount(unifiedOrder, s.id)
                    const badge = badges[s.id]
                    const isStub = badge === 'stub'
                    const emoji = BADGE_EMOJI[badge ?? 'real']
                    const title = buildTitle(
                      badge,
                      stubDeps[s.id] ?? '',
                      s.desc
                    )
                    return (
                      <button
                        key={s.id}
                        onClick={() => onAddSkill(s.id)}
                        disabled={isRunning || isStub}
                        title={title}
                        className={chip(count > 0, isRunning || isStub)}
                      >
                        <span
                          className={styles.skillBadge}
                          aria-label={`${badge ?? 'real'} skill`}
                        >
                          {emoji}
                        </span>
                        {getCheckedLabel(count, s.label)}
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
