// 後端呼叫的唯一入口。元件不直接 fetch。

import type { AnalyzeRequest, GraphDocument } from './types';

export class ApiError extends Error {}

export async function analyze(request: AnalyzeRequest): Promise<GraphDocument> {
  const response = await fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    // 後端刻意只回一句模糊的話（詳細原因在伺服器日誌裡），照原樣顯示即可。
    const detail = await response
      .json()
      .then((body: { detail?: string }) => body.detail)
      .catch(() => undefined);
    throw new ApiError(detail ?? `分析失敗（HTTP ${response.status}）`);
  }

  return (await response.json()) as GraphDocument;
}
