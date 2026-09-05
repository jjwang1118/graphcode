// 畫布的視覺定義。改樣式只會動到這個檔案。
//
// 編碼標準：**型別決定形狀、顏色與大小**，三者一致。大小不隨內容量變化——
// 「看到更細的東西」交給日後的縮放顆粒度，不靠節點大小表達。

export const palette = {
  background: '#0a0d14',
  panel: '#11151f',
  border: '#1e2536',
  text: '#c8d3e3',
  textDim: '#6b7a94',
  repo: '#f5c451',
  directory: '#7de2ff',
  file: '#5b6b8c',
  external: '#f0883e',
  //: `contains` 是骨架，`imports` 是依賴。除了亮度，再用色相分開——原本兩者都
  //: 是藍色系，只差明暗，實際看還是分不太出來
  edge: '#46705c',
  edgeImports: '#7aa2e3',
  danger: '#ff6b6b',
  accent: '#a78bfa',
};

export const graphStyle = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      color: palette.text,
      'font-size': 15,
      'font-family': 'ui-monospace, SFMono-Regular, Menlo, monospace',
      'text-valign': 'center' as const,
      'text-halign': 'right' as const,
      'text-margin-x': 9,
      'text-max-width': '200px',
      'text-wrap': 'ellipsis' as const,
      'text-outline-color': palette.background,
      'text-outline-width': 3,
      'background-color': palette.file,
      'border-width': 1,
      'border-color': palette.border,
      width: 15,
      height: 15,
      'transition-property': 'opacity, border-color, border-width',
      'transition-duration': 180,
    },
  },
  {
    selector: 'node[type = "file"]',
    style: { shape: 'ellipse' as const, 'background-color': palette.file },
  },
  {
    selector: 'node[type = "directory"]',
    style: {
      shape: 'round-rectangle' as const,
      'background-color': palette.directory,
      'background-opacity': 0.85,
      width: 26,
      height: 26,
      'font-size': 17,
    },
  },
  {
    selector: 'node[type = "repo"]',
    style: {
      shape: 'hexagon' as const,
      'background-color': palette.repo,
      width: 46,
      height: 46,
      'font-size': 20,
      'border-width': 2,
      'border-color': palette.repo,
    },
  },
  {
    selector: 'node[type = "external_package"]',
    style: {
      shape: 'diamond' as const,
      'background-color': palette.external,
      width: 20,
      height: 20,
      'font-size': 15,
    },
  },
  {
    // 解析失敗只改邊框——形狀與顏色仍歸型別管，否則「型別決定形狀」那條規則就破了
    selector: 'node[parseError]',
    style: {
      'border-width': 3,
      'border-color': palette.danger,
      'border-style': 'dashed' as const,
    },
  },
  {
    selector: 'edge',
    style: {
      width: 1.4,
      'line-color': palette.edge,
      'line-opacity': 0.9,
      'curve-style': 'bezier' as const,
      'target-arrow-shape': 'triangle' as const,
      'target-arrow-color': palette.edge,
      'arrow-scale': 0.7,
      'transition-property': 'opacity, line-color, width',
      'transition-duration': 180,
    },
  },
  {
    // 依賴與骨架**同樣粗**，只差顏色與箭頭。粗細留給「這條線代表幾筆」去表達，
    // 一個視覺頻道只講一件事。
    selector: 'edge[type = "imports"]',
    style: {
      'line-color': palette.edgeImports,
      'target-arrow-color': palette.edgeImports,
      'arrow-scale': 1.1,
    },
  },
  {
    // 聚合了幾筆就標幾——只有重疊時才標，免得每條線都掛一個 1。
    //
    // 粗細分段而不是連續映射：收到目錄層時權重可能上看數十，連續映射會出現巨
    // 帶。門檻也是照收合後的量級訂的——原本訂在 1/4/9，但目錄層有七成的邊都在
    // 那之上，等於每條線都「粗」，粗細就不帶訊息了。
    selector: 'edge[count > 1]',
    style: {
      label: 'data(count)',
      color: palette.textDim,
      'font-size': 12,
      'text-background-color': palette.background,
      'text-background-opacity': 0.85,
      'text-background-padding': '2px',
    },
  },
  { selector: 'edge[count > 2]', style: { width: 2 } },
  { selector: 'edge[count > 8]', style: { width: 2.8 } },
  { selector: 'edge[count > 20]', style: { width: 3.6 } },

  // ── 互動狀態 ────────────────────────────────────────────────
  { selector: '.dim', style: { opacity: 0.12 } },
  {
    selector: 'node.hl',
    style: { 'border-width': 3, 'border-color': palette.accent, opacity: 1 },
  },
  {
    selector: 'edge.hl',
    style: {
      'line-color': palette.accent,
      'target-arrow-color': palette.accent,
      width: 2,
      opacity: 1,
    },
  },
  {
    selector: 'node.match',
    style: {
      'border-width': 3,
      'border-color': palette.repo,
      color: palette.repo,
      opacity: 1,
    },
  },
  {
    selector: 'node:selected',
    style: { 'border-width': 3, 'border-color': palette.accent },
  },
];

// 縮圖不需要標籤與箭頭，畫得越輕越好。
export const minimapStyle = [
  {
    selector: 'node',
    style: {
      label: '',
      'background-color': palette.file,
      width: 6,
      height: 6,
      'border-width': 0,
    },
  },
  {
    selector: 'node[type = "directory"]',
    style: { 'background-color': palette.directory, width: 8, height: 8 },
  },
  {
    selector: 'node[type = "repo"]',
    style: { 'background-color': palette.repo, width: 12, height: 12 },
  },
  {
    selector: 'node[type = "external_package"]',
    style: { 'background-color': palette.external, width: 7, height: 7 },
  },
  {
    selector: 'edge',
    style: {
      width: 1,
      'line-color': palette.edge,
      'curve-style': 'haystack' as const,
      'target-arrow-shape': 'none' as const,
    },
  },
];
