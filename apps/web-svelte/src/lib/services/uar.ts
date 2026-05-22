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

  private headers(): Record<string, string> {
    const h: Record<string, string> = {
      'Content-Type': 'application/json',
    };
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
    onError?: (err: string) => void
  ): Promise<void> {
    const url = `${this.baseUrl}/api/uar/stream`;
    const resp = await fetch(url, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ goal, skills } as RunRequest),
    });

    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(
        body.detail?.message || `HTTP ${resp.status}`
      );
    }

    const reader = resp.body?.getReader();
    if (!reader) throw new Error('No response body');

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';

      for (const chunk of lines) {
        const match = chunk.match(/^data: (.+)$/m);
        if (match) {
          try {
            const event = JSON.parse(match[1]);
            onEvent(event);
          } catch {
            /* skip malformed */
          }
        }
      }
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
