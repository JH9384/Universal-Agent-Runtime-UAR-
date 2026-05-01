export type ParsedMarkdownNode = {
  localId: string;
  label: string;
  kind: "number" | "runtime" | "markdown" | "text";
  value: unknown;
  x: number;
  y: number;
};

export type ParsedMarkdownEdge = {
  id: string;
  from: string;
  to: string;
  label: string;
};

export type ParsedMarkdownGraph = {
  nodes: ParsedMarkdownNode[];
  edges: ParsedMarkdownEdge[];
};

const RUNTIME_ALIASES: Record<string, string> = {
  sum: "sum_contents",
  add: "sum_contents",
  count: "count_inputs",
  max: "max_contents",
  min: "min_contents",
  sort: "sort_contents",
  identity: "identity_value",
};

function isNumericLine(line: string) {
  return /^-?\d+(\.\d+)?$/.test(line.trim());
}

function runtimeNameFor(line: string) {
  const key = line.trim().toLowerCase();
  return RUNTIME_ALIASES[key] ?? null;
}

function cleanLine(line: string) {
  return line.replace(/^[-*]\s+/, "").trim();
}

export function parseMarkdownToGraph(markdown: string): ParsedMarkdownGraph {
  const lines = markdown
    .split("\n")
    .map(cleanLine)
    .filter((line) => line.length > 0 && !line.startsWith("#"));

  const nodes: ParsedMarkdownNode[] = [];
  const edges: ParsedMarkdownEdge[] = [];
  const pendingValueNodes: string[] = [];

  for (const line of lines) {
    const runtimeName = runtimeNameFor(line);

    if (isNumericLine(line)) {
      const localId = `md-number-${nodes.length}`;
      nodes.push({
        localId,
        label: line,
        kind: "number",
        value: Number(line),
        x: 120 + nodes.length * 40,
        y: 140 + nodes.length * 26,
      });
      pendingValueNodes.push(localId);
      continue;
    }

    if (runtimeName) {
      const localId = `md-runtime-${nodes.length}`;
      nodes.push({
        localId,
        label: runtimeName,
        kind: "runtime",
        value: runtimeName,
        x: 220,
        y: 220 + nodes.length * 28,
      });

      for (const source of pendingValueNodes.slice(-2)) {
        edges.push({
          id: `${source}-${localId}`,
          from: source,
          to: localId,
          label: "input",
        });
      }
      continue;
    }

    const localId = `md-text-${nodes.length}`;
    nodes.push({
      localId,
      label: line.length > 24 ? `${line.slice(0, 24)}…` : line,
      kind: "text",
      value: line,
      x: 120 + nodes.length * 30,
      y: 160 + nodes.length * 24,
    });
  }

  if (nodes.length === 0 && markdown.trim()) {
    nodes.push({
      localId: "md-document-0",
      label: "Markdown document",
      kind: "markdown",
      value: markdown,
      x: 120,
      y: 160,
    });
  }

  return { nodes, edges };
}
