"""圖層的例外。狀態碼由 API 層決定，這一層不認識 HTTP。"""


class BuildError(Exception):
    """組圖失敗：邊指向不存在的節點，或節點 id 重複。"""
