const API = import.meta.env.VITE_UAR_API_URL ?? "http://127.0.0.1:8000";

export type UarObject = {
  id: string;
  value: unknown;
  label: string;
  kind: string;
};

async function readJson(response: Response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body?.detail ?? `Request failed: ${response.status}`);
  }
  return body;
}

export async function createObject(content: unknown, attributes: Record<string, unknown> = {}): Promise<UarObject> {
  const response = await fetch(`${API}/objects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mediaType: "application/json",
      mode: "immutable",
      attributes: { schema: "uor.schema.object.v1", ...attributes },
      links: [],
      content,
    }),
  });
  const record = await readJson(response);
  return {
    id: record.digest,
    value: content,
    label: String(attributes.label ?? content),
    kind: String(attributes.type ?? "object"),
  };
}

export async function createNumber(value: number): Promise<UarObject> {
  return createObject(value, { type: "number", label: value });
}

export async function listRuntimes() {
  const response = await fetch(`${API}/runtimes`);
  return readJson(response);
}

export async function runRuntime(runtimeName: string, inputIds: string[]) {
  const response = await fetch(`${API}/agents/execution/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ runtimeName, inputs: inputIds, parameters: {} }),
  });
  return readJson(response);
}

export async function traceObject(digest: string) {
  const response = await fetch(`${API}/agents/lineage/trace?digest=${encodeURIComponent(digest)}`);
  return readJson(response);
}

export async function health() {
  const response = await fetch(`${API}/health`);
  return readJson(response);
}
