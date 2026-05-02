import { describe, expect, it } from "vitest";
import { parseMarkdownToGraph } from "./markdownParser";

describe("parseMarkdownToGraph", () => {
  it("turns numbers and sum into an executable intent graph", () => {
    const graph = parseMarkdownToGraph("5\n10\nsum");

    expect(graph.nodes).toHaveLength(3);
    expect(graph.nodes[0]).toMatchObject({ kind: "number", value: 5, label: "5" });
    expect(graph.nodes[1]).toMatchObject({ kind: "number", value: 10, label: "10" });
    expect(graph.nodes[2]).toMatchObject({ kind: "runtime", value: "sum_contents", label: "sum_contents" });

    expect(graph.edges).toEqual([
      { id: "md-number-0-md-runtime-2", from: "md-number-0", to: "md-runtime-2", label: "input" },
      { id: "md-number-1-md-runtime-2", from: "md-number-1", to: "md-runtime-2", label: "input" },
    ]);
  });

  it("maps runtime aliases deterministically", () => {
    expect(parseMarkdownToGraph("1\n2\nadd").nodes[2]).toMatchObject({ kind: "runtime", value: "sum_contents" });
    expect(parseMarkdownToGraph("1\n2\nmax").nodes[2]).toMatchObject({ kind: "runtime", value: "max_contents" });
    expect(parseMarkdownToGraph("1\n2\nmin").nodes[2]).toMatchObject({ kind: "runtime", value: "min_contents" });
  });

  it("keeps unknown lines as text nodes", () => {
    const graph = parseMarkdownToGraph("# Title\nhello world");
    expect(graph.nodes).toHaveLength(1);
    expect(graph.nodes[0]).toMatchObject({ kind: "text", value: "hello world" });
  });
});
