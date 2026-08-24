import { afterEach, describe, expect, it, vi } from 'vitest';

import { UARService } from './uar';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('UARService', () => {
  it('normalizes the base URL and returns registered skills', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ skills: ['section_sum'] }), {
        headers: { 'Content-Type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const service = new UARService('/api/');
    await expect(service.getSkills()).resolves.toEqual(['section_sum']);
    expect(fetchMock).toHaveBeenCalledWith('/api/uar/skills', {
      headers: {},
    });
  });

  it('parses split SSE chunks without losing event boundaries', async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"type":"sta'));
        controller.enqueue(encoder.encode('rt"}\n\ndata: {"type":"complete"}\n\n'));
        controller.close();
      },
    });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(body, { status: 200 }))
    );
    const events: Array<Record<string, unknown>> = [];

    await new UARService('').streamGoal('test', [], (event) => {
      events.push(event);
    });

    expect(events).toEqual([{ type: 'start' }, { type: 'complete' }]);
  });
});
