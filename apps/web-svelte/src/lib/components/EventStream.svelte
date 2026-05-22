<script lang="ts">
  export let events: Array<Record<string, unknown>> = [];

  $: reversed = [...events].reverse();
</script>

{#if events.length > 0}
  <div class="mt-6 rounded-lg border border-gray-700 bg-gray-900 p-4">
    <h2 class="mb-2 text-lg font-semibold">Events ({events.length})</h2>
    <div class="max-h-96 space-y-2 overflow-y-auto">
      {#each reversed as event}
        <div class="rounded bg-gray-800 p-2 text-sm">
          <span class="font-mono text-blue-400">{event.type}</span>
          {#if event.skill}
            <span class="ml-2 text-gray-400">{event.skill}</span>
          {/if}
          {#if event.error}
            <p class="mt-1 text-red-400">{event.error}</p>
          {/if}
        </div>
      {/each}
    </div>
  </div>
{/if}
