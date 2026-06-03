/** Shared UAR API service for the Svelte frontend.
 *
 * Encapsulates all HTTP and WebSocket communication with the UAR backend,
 * eliminating duplicated fetch logic across components.
 */

export interface UARConfig {
  baseUrl: string;
  token?: string;
}

export interface RunRequest {
  goal: string;
  skills?: string[];
  timeout_seconds?: number;
  metadata?: Record<string, unknown>;
}

export class UARService {
  private baseUrl: string;
  private token?: string;

  constructor(baseUrl: string, token?: string) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.token = token;
  }

  private headers(body?: BodyInit | null): Record<string, string> {
    const h: Record<string, string> = {};
    if (body != null) {
      h['Content-Type'] = 'application/json';
    }
    if (this.token) {
      h['Authorization'] = `Bearer ${this.token}`;
    }
    return h;
  }

  /** Stream a goal via Server-Sent Events. */
  async streamGoal(
    goal: string,
    skills: string[],
    onEvent: (event: Record<string, unknown>) => void,
    onError?: (err: string) => void,
    signal?: AbortSignal
  ): Promise<void> {
    const url = `${this.baseUrl}/api/uar/stream`;
    const body = JSON.stringify({ goal, skills } as RunRequest);
    const resp = await fetch(url, {
      method: 'POST',
      headers: this.headers(body),
      body,
      signal,
    });

    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      const msg = body.detail?.message || `HTTP ${resp.status}`;
      onError?.(msg);
      throw new Error(msg);
    }

    const reader = resp.body?.getReader();
    if (!reader) {
      const msg = 'No response body';
      onError?.(msg);
      throw new Error(msg);
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const parts = buffer.split(/\n\n|\r\n\r\n/);
        buffer = parts.pop() || '';

        for (const part of parts) {
          const dataLines: string[] = [];
          for (const line of part.split(/\r?\n/)) {
            if (line.startsWith('data:')) {
              dataLines.push(line.replace(/^data:\s?/, ''));
            }
          }
          if (dataLines.length > 0) {
            try {
              const event = JSON.parse(dataLines.join('\n'));
              onEvent(event);
            } catch (err) {
              onError?.(`Malformed event: ${String(err)}`);
            }
          }
        }
      }
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') {
        // Expected when user cancels; don't report as error
        return;
      }
      const msg = String(err);
      onError?.(msg);
      throw err;
    } finally {
      try { reader.cancel(); } catch {}
      try { reader.releaseLock(); } catch {}
    }
  }

  /** Fetch registered skills. */
  async getSkills(): Promise<string[]> {
    const resp = await fetch(`${this.baseUrl}/api/uar/skills`, {
      headers: this.headers(),
    });
    const body = await resp.json();
    return body.skills || [];
  }

  /** Fetch recipes. */
  async getRecipes(): Promise<
    Array<{ id: string; label: string; skills: string[]; hint: string }>
  > {
    const resp = await fetch(`${this.baseUrl}/api/uar/recipes`, {
      headers: this.headers(),
    });
    const body = await resp.json();
    return body.recipes || [];
  }
}
