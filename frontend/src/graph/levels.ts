// 層級 = 看多細。跟視圖（看哪種關係）是兩個不同的軸。
//
// 收合是**後端做的**（`app/graph/views.py`），前端只送一個數字——聚合是圖的運
// 算，硬性規則說前端不做。
//
// 為什麼需要：檔案層 98 個節點、135 條邊，其中 `models/__init__.py` 一個節點就
// 吃掉 59 條入邊，畫面上是蜘蛛網中心。收到目錄層剩 25 個節點、63 條邊，最忙的
// 只剩 7 條——因為「所有檔案都 import models」在目錄層本來就該是一條邊。

import type { ExternalMode } from '../api/types';
import type { LayoutId } from './layouts';

export interface LevelOption {
  /** 送給後端的 `level`；`null` 代表不收合。 */
  value: number | null;
  label: string;
}

// 由粗到細。
//
// **哪一層好看取決於專案的形狀**，不是固定的：codegraph 的程式碼埋在
// `backend/app/…` 底下，所以第 3 層才開始有東西看（71 節點 / 63 條 imports）；
// 第 2 層會把整個 `backend/app` 收成一個點，內部依賴全變成節點上的計數。扁平
// 的專案則會在第 1 層就分開。所以層數開到 5，讓人自己找甜蜜點。
export const levels: LevelOption[] = [
  { value: 0, label: '整個專案' },
  { value: 1, label: '第 1 層目錄' },
  { value: 2, label: '第 2 層目錄' },
  { value: 3, label: '第 3 層目錄' },
  { value: 4, label: '第 4 層目錄' },
  { value: 5, label: '第 5 層目錄' },
  { value: null, label: '檔案（最細）' },
];

export const externalLabels: Record<ExternalMode, string> = {
  full: '每個套件一個節點',
  grouped: '合成一個，可展開',
  hidden: '隱藏',
};

/** 收合後的層級不是樹狀好看的形狀（有環、會交叉），一律用力導向。 */
export function layoutFor(level: number | null): LayoutId {
  return level === null ? 'left-right' : 'force';
}

/** `<select>` 只吃字串，`null` 沒辦法當 value。 */
export function levelKey(level: number | null): string {
  return level === null ? 'file' : String(level);
}

export function levelFromKey(key: string): number | null {
  return key === 'file' ? null : Number(key);
}
