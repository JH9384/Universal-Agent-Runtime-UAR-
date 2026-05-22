<script lang="ts">
  export let selected: string[] = [];

  const skills = [
    'section_sum',
    'doc_ingest',
    'dependency_map',
    'ollama_generate',
    'graphrag_skills',
  ];

  function toggle(skill: string) {
    selected = selected.includes(skill)
      ? selected.filter((s) => s !== skill)
      : [...selected, skill];
  }
</script>

<div class="mb-4">
  <label class="mb-1 block text-sm font-medium">Skills</label>
  <div class="flex flex-wrap gap-2">
    {#each skills as skill}
      <button
        on:click={() => toggle(skill)}
        class="rounded-full border px-3 py-1 text-sm transition-colors"
        class:bg-blue-600={selected.includes(skill)}
        class:border-gray-700={!selected.includes(skill)}
      >
        {skill}
      </button>
    {/each}
  </div>
</div>
