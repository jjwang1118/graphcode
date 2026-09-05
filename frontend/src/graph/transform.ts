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

export interface CytoscapeEdge {
  data: {
    id: string;
    source: string;
    target: string;
    type: EdgeType;
    /** 聚合了幾筆。1 代表沒有重疊。 */
    count: number;
    /** 每一筆的名字與行號，給 hover 展開用。 */
    detail: string;
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
      existing.data.count += 1;
      existing.data.detail += `\n${describe(edge)}`;
      continue;
    }
    merged.set(id, {
      data: {
        id,
        source: edge.source,
        target: edge.target,
        type: edge.type,
        count: 1,
        detail: describe(edge),
      },
    });
  }

  return [...merged.values()];
}

function describe(edge: Edge): string {
  const name = edge.properties.name;
  const line = edge.properties.line;
  const parts = [typeof name === 'string' ? name : null, typeof line === 'number' ? `行 ${line}` : null];
  return parts.filter(Boolean).join(' ');
}
