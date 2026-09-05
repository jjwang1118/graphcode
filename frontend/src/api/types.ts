// 對應 backend/app/models/。契約定義見 docs/backend/graph_schema.md。
//
// 目前靠人工與後端同步：改了 pydantic model 就必須改這裡，沒有任何機制會
// 在漂移時讓編譯失敗。機械保證留到 plan 1.7，屆時改為從 OpenAPI 生成。

export type NodeType =
  | 'repo'
  | 'directory'
  | 'file'
  | 'external_package'
  | 'module'
  | 'class'
  | 'function';

export type EdgeType =
  | 'contains'
  | 'imports'
  | 'defines'
  | 'calls'
  | 'inherits';

export interface Node {
  id: string;
  type: NodeType;
  label: string;
  properties: Record<string, unknown>;
}

export interface Edge {
  source: string;
  target: string;
  type: EdgeType;
  properties: Record<string, unknown>;
}

export interface Meta {
  node_count: number;
  edge_count: number;
  cycles: string[][];
  isolated_nodes: string[];
  /** 解析失敗的檔案數。哪幾個看 file 節點的 `properties.parse_error`。 */
  parse_failures: number;
  /** 從多個候選裡挑出來的 imports 邊數。哪幾條看邊的 `properties.ambiguous`。 */
  ambiguous_imports: number;
  /** 爬出專案外、沒有產生邊的相對 import 筆數。 */
  unresolved_imports: number;
  /** ISO 8601 字串。JSON 沒有 datetime，不會自動變成 Date。 */
  analyzed_at: string | null;
}

export interface GraphDocument {
  nodes: Node[];
  edges: Edge[];
  meta: Meta;
}

/** `POST /api/analyze` 的 body。`edge_types` 省略＝整張圖。 */
export interface AnalyzeRequest {
  path: string;
  edge_types?: EdgeType[];
}
