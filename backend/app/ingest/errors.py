"""ingest 層的例外。狀態碼由 API 層決定，這一層不認識 HTTP。"""


class IngestError(Exception):
    """取得根目錄失敗。

    訊息含絕對路徑，只供日誌使用，不可原樣回傳給前端。
    """
