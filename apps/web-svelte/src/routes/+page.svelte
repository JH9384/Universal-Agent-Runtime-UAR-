<script lang="ts">
  import { onMount } from 'svelte';
  import { UARService } from '$services/uar';
  import SkillSelector from '$components/SkillSelector.svelte';
  import EventStream from '$components/EventStream.svelte';

  let goal = '';
  let selectedSkills: string[] = [];
  let events: any[] = [];
  let running = false;
  let uar: UARService;

  onMount(() => {
    uar = new UARService('/api');
  });

  async function run() {
    if (!goal.trim() || running) return;
    running = true;
    events = [];
    try {
      await uar.streamGoal(
        goal,
        selectedSkills,
        (ev) => { events = [...events, ev]; }
      );
    } finally {
      running = false;
    }
  }
</script>

<main class="mx-auto max-w-4xl p-6">
  <h1 class="mb-6 text-3xl font-bold">Universal Agent Runtime</h1>

  <div class="mb-4">
    <label class="mb-1 block text-sm font-medium">Goal</label>
    <textarea
      bind:value={goal}
      class="w-full rounded-lg border border-gray-700 bg-gray-900 p-3"
      rows="3"
      placeholder="Describe what you want the agent to do..."
    ></textarea>
  </div>

  <SkillSelector bind:selected={selectedSkills} />

  <button
    on:click={run}
    disabled={running || !goal.trim()}
    class="mt-4 rounded-lg bg-blue-600 px-6 py-2 font-semibold disabled:opacity-50"
  >
    {running ? 'Running...' : 'Run'}
  </button>

  <EventStream {events} />
</main>
