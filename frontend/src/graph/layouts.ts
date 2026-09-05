// 排版方式。每一種就是一組 Cytoscape layout 參數，換排版不改元件。
//
// 節點間距**不在這裡**：`spacingFactor` 不是等比例撐開整張圖，調它只有部分
// 層次會動。間距改由 GraphCanvas 在排完之後統一縮放座標，見 `rescale()`。

import type { LayoutOptions } from 'cytoscape';

export type LayoutId = 'top-down' | 'left-right' | 'radial' | 'force';

export const layoutLabels: Record<LayoutId, string> = {
  'top-down': '由上往下',
  'left-right': '由左往右',
  radial: '放射',
  force: '力導向（會晃動）',
};

// 層與層之間的距離就是線的長度，比同層之間再拉開一點。
const DEPTH_STRETCH = 1.8;

export function layoutOptions(id: LayoutId, fit: boolean): LayoutOptions {
  if (id === 'force') {
    return {
      name: 'cose',
      animate: true,
      animationDuration: 900,
      nodeRepulsion: () => 12000,
      idealEdgeLength: () => 90,
      nodeOverlap: 20,
      fit,
      padding: 40,
    };
  }

  return {
    name: 'breadthfirst',
    directed: true,
    spacingFactor: 1.1,
    circle: id === 'radial',
    nodeDimensionsIncludeLabels: true,
    animate: true,
    animationDuration: 400,
    fit,
    padding: 40,
    transform:
      id === 'left-right'
        ? // 由左往右：座標軸對調，對調後 x 才是深度方向。
          (_node, position) => ({ x: position.y * DEPTH_STRETCH, y: position.x })
        : id === 'top-down'
          ? (_node, position) => ({ x: position.x, y: position.y * DEPTH_STRETCH })
          : // 放射狀不拉伸，否則圓會被壓成橢圓。
            undefined,
  };
}
