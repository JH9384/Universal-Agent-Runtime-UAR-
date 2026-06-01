import { useMemo } from 'react'
import { useApiFetch } from '../hooks/useApiFetch'
import styles from './TopologyWidget.module.css'

interface SkillHealth {
  name: string
  available: boolean
}

interface SkillItem {
  id: string
  label: string
  desc?: string
  category?: string
}

interface RecipeItem {
  id: string
  skills: string[]
  label?: string
}

interface SkillsApiResponse {
  skills?: SkillItem[]
  [key: string]: unknown
}

interface RecipesApiResponse {
  recipes?: RecipeItem[]
  [key: string]: unknown
}

interface HealthApiResponse {
  skills?: SkillHealth[]
  [key: string]: unknown
}

const SKILL_GROUPS: Record<string, string[]> = {
  'Document Ingest': ['doc_ingest', 'doc_ingest_enhanced'],
  'Code Analysis': ['dependency_map', 'code_analysis', 'section_sum', 'sum_review'],
  'Math / Plot': ['math_compute', 'math_plot', 'math_plot_3d'],
  'Physics': ['physics_compute'],
  'Quantum': ['quantum_circuit', 'quantum_ml'],
  'RISC-V': ['riscv_sim', 'riscv_cycle'],
  'Verilog / FPGA': ['verilator_sim', 'fpga_build'],
  'Machine Learning': ['ml_tools', 'mlops_security'],
  'LLM': ['ollama_generate', 'anthropic_skills', 'gemini_skills', 'llm_base'],
  'GraphRAG': ['graphrag_local', 'graphrag_global', 'graphrag_skills'],
  'Blockchain': ['cipher_ops', 'blockchain'],
  'Autonomi': ['autonomi_storage'],
  'UOR Ecosystem': ['uor_address', 'uor_witness', 'uor_ecosystem_skills'],
  'Data Viz': ['data_viz_3d', 'trefoil_simulation'],
  'Molecular': ['molecular_visualizer'],
  'Extended': ['advanced_integrations', 'alias_skills', 'atomic_lang_model'],
}

function findCategory(skillId: string): string {
  for (const [cat, ids] of Object.entries(SKILL_GROUPS)) {
    if (ids.includes(skillId)) return cat
  }
  return 'Other'
}

function SkillNode({ skill, health }: { skill: SkillItem; health?: SkillHealth }) {
  const isHealthy = health?.available ?? true
  return (
    <div className={styles.skillNode}>
      <span className={`${styles.healthDot} ${isHealthy ? styles.dotGreen : styles.dotRed}`} />
      <span className={styles.skillName}>{skill.label || skill.id}</span>
    </div>
  )
}

function RecipeCard({ recipe, skills, healthMap }: {
  recipe: RecipeItem
  skills: SkillItem[]
  healthMap: Record<string, boolean>
}) {
  const recipeSkills = useMemo(() => {
    return recipe.skills
      .map((sid) => skills.find((s) => s.id === sid))
      .filter(Boolean) as SkillItem[]
  }, [recipe.skills, skills])

  const allHealthy = recipeSkills.every((s) => healthMap[s.id] ?? true)

  return (
    <div className={styles.recipeCard}>
      <div className={styles.recipeHeader}>
        <span className={styles.recipeIcon}>🍳</span>
        <span className={styles.recipeName}>{recipe.id}</span>
        <span className={`${styles.recipeStatus} ${allHealthy ? styles.statusOk : styles.statusWarn}`}>
          {allHealthy ? 'Ready' : 'Degraded'}
        </span>
      </div>
      <div className={styles.recipeSkills}>
        {recipeSkills.map((s) => (
          <span key={s.id} className={styles.recipeSkillChip}>
            {s.label || s.id}
          </span>
        ))}
      </div>
    </div>
  )
}

export function TopologyWidget() {
  const { data: skillsData } = useApiFetch<SkillsApiResponse>('/api/uar/skills')
  const { data: recipesData } = useApiFetch<RecipesApiResponse>('/api/uar/recipes')
  const { data: healthData } = useApiFetch<HealthApiResponse>('/api/health/dashboard')

  const skills = skillsData?.skills || []
  const recipes = recipesData?.recipes || []

  const healthMap = useMemo(() => {
    const map: Record<string, boolean> = {}
    healthData?.skills?.forEach((s) => {
      map[s.name] = s.available
    })
    return map
  }, [healthData])

  // Group skills by category
  const groupedSkills = useMemo(() => {
    const groups: Record<string, SkillItem[]> = {}
    skills.forEach((skill) => {
      const cat = findCategory(skill.id)
      if (!groups[cat]) groups[cat] = []
      groups[cat].push(skill)
    })
    return groups
  }, [skills])

  // Recipe → skill edge matrix
  const recipeSkillMatrix = useMemo(() => {
    const matrix: Record<string, string[]> = {}
    recipes.forEach((r) => {
      matrix[r.id] = r.skills || []
    })
    return matrix
  }, [recipes])

  return (
    <div className={styles.topologyWidget}>
      {/* Skill Registry Graph */}
      <div className={styles.topologySection}>
        <h4 className={styles.sectionTitle}>Skill Registry</h4>
        <p className={styles.sectionDesc}>
          {skills.length} skills registered · {recipes.length} recipes defined
        </p>

        {Object.entries(groupedSkills).map(([category, catSkills]) => (
          <div key={category} className={styles.categoryBlock}>
            <h5 className={styles.categoryName}>{category}</h5>
            <div className={styles.skillGrid}>
              {catSkills.map((skill) => (
                <SkillNode
                  key={skill.id}
                  skill={skill}
                  health={healthData?.skills?.find((h) => h.name === skill.id)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Recipe Network */}
      {recipes.length > 0 && (
        <div className={styles.topologySection}>
          <h4 className={styles.sectionTitle}>Recipe Network</h4>
          <p className={styles.sectionDesc}>
            {recipes.length} recipes · click a recipe to see its skill composition
          </p>
          <div className={styles.recipeGrid}>
            {recipes.map((recipe) => (
              <RecipeCard
                key={recipe.id}
                recipe={recipe}
                skills={skills}
                healthMap={healthMap}
              />
            ))}
          </div>
        </div>
      )}

      {/* Edge Summary */}
      {recipes.length > 0 && (
        <div className={styles.topologySection}>
          <h4 className={styles.sectionTitle}>Edge Summary</h4>
          <div className={styles.edgeStats}>
            <div className={styles.edgeStat}>
              <span className={styles.edgeStatValue}>{skills.length}</span>
              <span className={styles.edgeStatLabel}>Skill Nodes</span>
            </div>
            <div className={styles.edgeStat}>
              <span className={styles.edgeStatValue}>{recipes.length}</span>
              <span className={styles.edgeStatLabel}>Recipe Nodes</span>
            </div>
            <div className={styles.edgeStat}>
              <span className={styles.edgeStatValue}>
                {Object.values(recipeSkillMatrix).flat().length}
              </span>
              <span className={styles.edgeStatLabel}>Skill Edges</span>
            </div>
            <div className={styles.edgeStat}>
              <span className={styles.edgeStatValue}>
                {Object.keys(healthMap).filter((k) => healthMap[k]).length}
              </span>
              <span className={styles.edgeStatLabel}>Healthy Skills</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
