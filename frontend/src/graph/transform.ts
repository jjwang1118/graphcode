// API 形狀 → Cytoscape elements。轉換集中在這裡，元件不直接碰 API 型別。
//
// 這個檔案刻意不 import cytoscape：它是純函式，能單獨測試，也不必等畫布元件
// 存在才能寫。

import type { Edge, EdgeType, GraphDocument, NodeType } from '../api/types';

export interface CytoscapeNode {
  data: {
    id: string;
    label: string;
    type: NodeType;
    /** 解析失敗的原因。有值才會被畫成紅色虛線框。 */
    parseError?: string;
  };
}

/** 聚合掉的一筆筆 import，依「來源檔 → 目標檔 → 行號」分組。 */
export interface ImportDetail {
  /** 來源檔案的 id */
  from: string;
  /** 目標檔案或外部套件的 id */
  to: string;
  /** 寫在原始碼第幾行。同一個 `from x import a, b` 的名字共用一行 */
  line: number | null;
  /** 這一對之間 import 了哪些名字 */
  names: string[];
}

export interface CytoscapeEdge {
  data: {
    id: string;
    source: string;
    target: string;
    type: EdgeType;
    /** 聚合了幾筆。1 代表沒有重疊。 */
    count: number;
    /** 聚合掉的細節，給訊息框用。 */
    details: ImportDetail[];
  };
}

export interface CytoscapeElements {
  nodes: CytoscapeNode[];
  edges: CytoscapeEdge[];
}

export function toElements(document: GraphDocument): CytoscapeElements {
  return {
    nodes: document.nodes.map(toNode),
    edges: aggregate(document.edges),
  };
}

function toNode(node: GraphDocument['nodes'][number]): CytoscapeNode {
  const parseError = node.properties.parse_error;
  return {
    data: {
      id: node.id,
      label: node.label,
      type: node.type,
      ...(typeof parseError === 'string' ? { parseError } : {}),
    },
  };
}

// 同一對節點之間的同型別邊聚合成一條。
//
// `from app.models import Edge, EdgeType, Node` 在後端是三筆事實、三條邊——那
// 是刻意的，資料層不該先把資訊丟掉。但畫出來是三條完全重疊的線，看起來像一條
// 特別濃的關係。所以**聚合在視圖層做**：畫一條，把細節收進 data。
//
// 實測本專案：231 條 imports 邊聚合後剩 135 條，42% 的線是重疊的。
function aggregate(edges: Edge[]): CytoscapeEdge[] {
  const merged = new Map<string, CytoscapeEdge>();

  for (const edge of edges) {
    const id = `${edge.type}:${edge.source}->${edge.target}`;
    const existing = merged.get(id);
    if (existing) {
      existing.data.count += weightOf(edge);
      addDetails(existing.data.details, edge);
      continue;
    }
    const details: ImportDetail[] = [];
    addDetails(details, edge);
    merged.set(id, {
      data: {
        id,
        source: edge.source,
        target: edge.target,
        type: edge.type,
        count: weightOf(edge),
        details,
      },
    });
  }

  return [...merged.values()];
}

// 收合過的邊後端已經合併好，帶著 `weight`；沒收合的一筆就是一。
function weightOf(edge: Edge): number {
  const weight = edge.properties.weight;
  return typeof weight === 'number' ? weight : 1;
}

// 細節有兩種來源，結果是同一個型別：
//   收合層 —— 後端 `views.py` 把收掉的原始邊放在 `properties.sources`
//   檔案層 —— 沒有 sources，這條邊自己就是一筆
//
// **這是唯一認識後端形狀的地方。** 之後改成打 API 去全量圖查（plan 4.4），只
// 要換 `rawSources()`，分組與顯示都不用動。
function addDetails(into: ImportDetail[], edge: Edge): void {
  // 只有 imports 有細節可說。`contains` 的「細節」換個層級就看得到，後端也不
  // 送 sources，硬湊只會讓框裡出現一堆沒有意義的名字。
  if (edge.type !== 'imports') return;

  for (const one of rawSources(edge)) {
    // 行號進分組的 key：同一對檔案在兩行各 import 一次，就該是兩組
    const found = into.find(
      (detail) =>
        detail.from === one.from && detail.to === one.to && detail.line === one.line,
    );
    if (found) found.names.push(one.name);
    else into.push({ from: one.from, to: one.to, line: one.line, names: [one.name] });
  }
}

interface RawSource {
  from: string;
  to: string;
  line: number | null;
  name: string;
}

function rawSources(edge: Edge): RawSource[] {
  const sources = edge.properties.sources;
  if (!Array.isArray(sources)) {
    return [
      {
        from: edge.source,
        to: edge.target,
        line: lineOf(edge.properties),
        name: nameOf(edge.properties),
      },
    ];
  }
  return sources.filter(isRecord).map((one) => ({
    from: String(one.from),
    to: String(one.to),
    line: lineOf(one),
    name: nameOf(one),
  }));
}

// `from app.models import Edge` 給 `Edge`；`import os` 沒有 name，退回模組字串
// ——否則那種 import 在框裡會是一片空白。
function nameOf(properties: Record<string, unknown>): string {
  const name = properties.name;
  if (typeof name === 'string') return name;
  const module = properties.module;
  return typeof module === 'string' ? module : '?';
}

function lineOf(properties: Record<string, unknown>): number | null {
  const line = properties.line;
  return typeof line === 'number' ? line : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}
