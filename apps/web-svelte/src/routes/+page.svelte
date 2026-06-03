<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { UARService } from '$services/uar';
  import SkillSelector from '$components/SkillSelector.svelte';
  import EventStream from '$components/EventStream.svelte';

  const MAX_EVENTS = 1000;

  let goal = '';
  let selectedSkills: string[] = [];
  let events: any[] = [];
  let running = false;
  let streamError: string | null = null;
  let uar: UARService;
  let abortCtrl: AbortController | null = null;

  onMount(() => {
    uar = new UARService('/api');
  });

  onDestroy(() => {
    abortCtrl?.abort();
  });

  async function run() {
    if (!goal.trim() || running) return;
    running = true;
    streamError = null;
    events = [];
    abortCtrl = new AbortController();

    try {
      await uar.streamGoal(
        goal,
        selectedSkills,
        (ev) => {
          events = [...events, ev];
          if (events.length > MAX_EVENTS) {
            events = events.slice(-MAX_EVENTS);
          }
        },
        (err) => { streamError = err; },
        abortCtrl.signal
      );
    } catch (err) {
      if ((err as Error)?.name !== 'AbortError') {
        streamError = String(err);
      }
    } finally {
      running = false;
      abortCtrl = null;
    }
  }
</script>

<main class="mx-auto max-w-4xl p-6">
  <h1 class="mb-6 text-3xl font-bold">Universal Agent Runtime</h1>

  <div class="mb-4">
    <label for="goal-input" class="mb-1 block text-sm font-medium">Goal</label>
    <textarea
      id="goal-input"
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

  {#if streamError}
    <div class="mt-4 rounded-lg border border-red-700 bg-red-900/30 p-3 text-sm text-red-300">
      {streamError}
    </div>
  {/if}

  <EventStream {events} />
</main>
