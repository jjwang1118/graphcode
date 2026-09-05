// 視圖 = 同一張圖的查詢條件。
//
// 切換「目錄樹 / 依賴圖」**不是換元件，是換送給後端的 `edge_types`**。前端不做
// 任何圖的運算，篩選由後端負責——這是 plan 2.7 的驗收點：如果為了畫依賴圖得改
// 前端結構，就是模型設計有問題。

import type { EdgeType } from '../api/types';
import type { LayoutId } from './layouts';

export type ViewId = 'all' | 'tree' | 'imports';

export const viewLabels: Record<ViewId, string> = {
  all: '全部',
  tree: '目錄樹',
  imports: '依賴圖',
};

/** 送給 `POST /api/analyze` 的 `edge_types`；`undefined` 代表整張圖。 */
export const viewEdgeTypes: Record<ViewId, EdgeType[] | undefined> = {
  all: undefined,
  tree: ['contains'],
  imports: ['imports'],
};

/** 換視圖時自動換的排版。`contains` 是樹，其餘有環，樹狀排版不適用。 */
export const viewLayout: Record<ViewId, LayoutId> = {
  all: 'force',
  tree: 'left-right',
  imports: 'force',
};
