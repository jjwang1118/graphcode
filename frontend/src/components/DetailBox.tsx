// 釘在畫布上的細節框：一條聚合過的邊背後是哪些檔案在 import 什麼。
//
// 純顯示 ＋ 自己負責關閉。畫布只管「開」——算出座標、把 details 交給它——所以
// GraphCanvas 與 Graph3D 都不必寫關閉的 handler，兩個畫布共用同一個框。

import { useEffect, useLayoutEffect, useRef, useState } from 'react';

import { palette } from '../graph/style';
import type { ImportDetail } from '../graph/transform';

interface Props {
  /** 點擊處，相對於畫布容器 */
  x: number;
  y: number;
  details: ImportDetail[];
  onClose: () => void;
}

//: 框與點擊處的距離，讓游標不壓在框上
const OFFSET = 12;
//: 框貼到容器邊緣時至少留這麼多
const MARGIN = 8;

export function DetailBox({ x, y, details, onClose }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const [at, setAt] = useState({ x: x + OFFSET, y: y + OFFSET });

  // 框外按下就關。
  //
  // 監聽掛在 effect 裡是刻意的：effect 在 commit 之後才跑，開啟這個框的那次
  // 點擊早就傳播完了，所以不會一開就把自己關掉。
  useEffect(() => {
    function onDown(event: PointerEvent) {
      if (!box.current?.contains(event.target as Node)) onClose();
    }
    document.addEventListener('pointerdown', onDown);
    return () => document.removeEventListener('pointerdown', onDown);
  }, [onClose]);

  // 點在畫布右下角時框會超出去，量完自己的尺寸再往回收。用 layout effect 才
  // 不會先閃一下錯的位置。
  //
  // 順便重播出現動畫：點另一條邊時這個元件沒有卸載重建，CSS animation 不會自
  // 己再跑一次，得把它歸零、逼瀏覽器重算版面、再放回去。
  useLayoutEffect(() => {
    const self = box.current;
    const parent = self?.offsetParent as HTMLElement | null;
    if (!self || !parent) return;

    setAt({
      x: clamp(x + OFFSET, self.offsetWidth, parent.clientWidth),
      y: clamp(y + OFFSET, self.offsetHeight, parent.clientHeight),
    });

    self.style.animation = 'none';
    void self.offsetWidth;
    self.style.animation = '';
  }, [x, y, details]);

  return (
    <div
      ref={box}
      style={{
        position: 'absolute',
        left: at.x,
        top: at.y,
        maxWidth: 320,
        maxHeight: 260,
        overflowY: 'auto',
        background: palette.panel,
        // 框浮在圖上，不是圖的一部分——亮邊才分得出前後層次
        border: `1px solid ${palette.borderBright}`,
        borderRadius: 6,
        boxShadow: '0 4px 16px rgba(0,0,0,0.45)',
        animation: 'detail-in 120ms ease-out',
        transformOrigin: 'top left',
        padding: '8px 10px',
        fontSize: 11,
        lineHeight: 1.5,
        color: palette.text,
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
        zIndex: 10,
      }}
    >
      {details.map((detail) => (
        <div key={`${detail.from}->${detail.to}@${detail.line}`} style={{ marginBottom: 6 }}>
          <div style={{ color: palette.textDim }}>
            {shortName(detail.from)} → {shortName(detail.to)}
            {detail.line !== null && <span style={{ marginLeft: 8 }}>行 {detail.line}</span>}
          </div>
          <div>{detail.names.join(', ')}</div>
        </div>
      ))}
    </div>
  );
}

function clamp(wanted: number, size: number, limit: number): number {
  return Math.max(MARGIN, Math.min(wanted, limit - size - MARGIN));
}

// id 是 `file:backend/app/graph/build.py` 這種，框裡只要最後一段。
// `__init__.py` 光看檔名分不出是誰的，多帶一層目錄。
function shortName(id: string): string {
  const path = id.slice(id.indexOf(':') + 1);
  const parts = path.split('/');
  const last = parts[parts.length - 1];
  return last === '__init__.py' && parts.length > 1
    ? `${parts[parts.length - 2]}/${last}`
    : last;
}
