export type ParsedMarkdownNode = {
  localId: string;
  label: string;
  kind: "number" | "runtime" | "markdown" | "text" | "section";
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

type MarkdownSection = {
  title: string;
  level: number;
  body: string[];
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

function headingFor(line: string) {
  const match = /^(#{1,6})\s+(.+)$/.exec(line.trim());
  if (!match) return null;
  return { level: match[1].length, title: match[2].trim() };
}

export function chunkMarkdownSections(markdown: string): MarkdownSection[] {
  const sections: MarkdownSection[] = [];
  let current: MarkdownSection | null = null;

  for (const rawLine of markdown.split("\n")) {
    const heading = headingFor(rawLine);
    if (heading) {
      current = { title: heading.title, level: heading.level, body: [] };
      sections.push(current);
      continue;
    }

    if (!current) {
      current = { title: "Document", level: 0, body: [] };
      sections.push(current);
    }

    if (rawLine.trim()) current.body.push(rawLine);
  }

  return sections.filter((section) => section.title !== "Document" || section.body.length > 0);
}

export function parseMarkdownToGraph(markdown: string): ParsedMarkdownGraph {
  const sections = chunkMarkdownSections(markdown);
  const nodes: ParsedMarkdownNode[] = [];
  const edges: ParsedMarkdownEdge[] = [];
  const pendingValueNodes: string[] = [];
  let activeSectionId: string | null = null;

  const addSectionNode = (section: MarkdownSection, index: number) => {
    const localId = `md-section-${index}`;
    nodes.push({
      localId,
      label: section.title,
      kind: "section",
      value: {
        title: section.title,
        level: section.level,
        body: section.body.join("\n"),
      },
      x: 80,
      y: 100 + nodes.length * 92,
    });
    return localId;
  };

  const parseContentLine = (line: string, sectionId: string | null) => {
    const cleaned = cleanLine(line);
    if (!cleaned) return;

    const runtimeName = runtimeNameFor(cleaned);

    if (isNumericLine(cleaned)) {
      const localId = `md-number-${nodes.length}`;
      nodes.push({
        localId,
        label: cleaned,
        kind: "number",
        value: Number(cleaned),
        x: 260 + nodes.length * 28,
        y: 140 + nodes.length * 34,
      });
      pendingValueNodes.push(localId);
      if (sectionId) edges.push({ id: `${sectionId}-${localId}`, from: sectionId, to: localId, label: "contains" });
      return;
    }

    if (runtimeName) {
      const localId = `md-runtime-${nodes.length}`;
      nodes.push({
        localId,
        label: runtimeName,
        kind: "runtime",
        value: runtimeName,
        x: 420,
        y: 180 + nodes.length * 34,
      });
      if (sectionId) edges.push({ id: `${sectionId}-${localId}`, from: sectionId, to: localId, label: "contains" });

      for (const source of pendingValueNodes.slice(-2)) {
        edges.push({
          id: `${source}-${localId}`,
          from: source,
          to: localId,
          label: "input",
        });
      }
      return;
    }

    const localId = `md-text-${nodes.length}`;
    nodes.push({
      localId,
      label: cleaned.length > 24 ? `${cleaned.slice(0, 24)}…` : cleaned,
      kind: "text",
      value: cleaned,
      x: 260 + nodes.length * 24,
      y: 160 + nodes.length * 30,
    });
    if (sectionId) edges.push({ id: `${sectionId}-${localId}`, from: sectionId, to: localId, label: "contains" });
  };

  for (const [sectionIndex, section] of sections.entries()) {
    activeSectionId = section.title === "Document" && section.level === 0 ? null : addSectionNode(section, sectionIndex);

    for (const line of section.body) {
      parseContentLine(line, activeSectionId);
    }
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
