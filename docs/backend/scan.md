# scan.md

走訪根目錄，把檔案系統變成節點與 `contains` 邊。

各階段職責見 CLAUDE.md › 架構 › scan；節點 id 規則見 `graph_schema.md`。

---

## 產出

```
sample/                          repo:.            （label: sample）
├── src/          →              ├── dir:src
│   └── app.py                   │   └── file:src/app.py
└── README.md                    └── file:README.md
```

四個節點、三條 `contains` 邊，剛好一棵樹。

| 欄位 | 內容 |
|---|---|
| `nodes` | `repo` / `directory` / `file` 節點，直接用 `app/models/` 的 `Node` |
| `edges` | `contains` 邊，只連直接的下一層 |
| `files` | 所有未被忽略的檔案的相對路徑，給之後的 parse 用 |

`files` 可以從 `nodes` 篩出來，仍然明列 —— parse 不必知道「節點有型別這回事」就能拿到它要的清單。

**scan 跑完時，圖的 `contains` 那一半就完整了**；後面幾個階段只補 `imports` 那一半。

---

## 忽略規則

預設跳過：`.git`、`node_modules`、`__pycache__`、`dist`、`build`、`.venv`、`.mypy_cache`、`.pytest_cache`、`.ruff_cache`。

被忽略的東西**連節點都不產生**，不是產了再隱藏。

| 設計 | 為什麼 |
|---|---|
| 清單以參數傳入，預設值是上面那組 | 之後要改成讀專案自己的 `.gitignore`，只換餵進來的東西，`walk.py` 不動 |
| 單獨放 `ignore.py` | 這是整個 scan 最可能被替換掉的部分 |
| 只比對**名字完全相符**，不做 `*.pyc` 樣式比對 | 忽略掉 `__pycache__` 整個目錄，`.pyc` 就一起沒了。樣式比對等真的需要再加 |

這是**雜訊過濾**，與安全無關 —— 安全的閘門在 ingest。兩者刻意分開，混在一起之後就分不出哪條規則是為了擋攻擊。

---

## symlink 一律跳過

連節點都不產生。這補的是 `ingest.md` 留下的洞：ingest 只檢查入口那一個路徑。

| 問題 | 說明 |
|---|---|
| 逃逸 | allowlist 內的捷徑指向 `/etc`，走訪時就出去了 |
| 無限遞迴 | 捷徑指回自己的祖先目錄，走訪永遠走不完 |

不採「產節點但不遞迴」，是因為 `contains` 要求**每個節點恰好一個父**。一個指向別處的捷徑要掛在哪棵樹上沒有好答案，不如不進圖。

同理，既不是目錄也不是一般檔案的東西（socket、FIFO）也跳過。

---

## 其他規則

| 規則 | 為什麼 |
|---|---|
| 每一層都 `sorted()` 後才走訪 | 檔案系統不保證回傳順序。不排序的話同一個 repo 跑兩次會產出不同的 JSON，golden 測試與 git diff 會一直髒 |
| 空目錄照樣產節點 | 它仍是目錄樹的一部分。不產的話，畫出來的樹跟使用者在檔案總管看到的不一樣 |
| `properties` 留空 | 行數、語言要開檔案讀，而 scan「不需要解析原始碼」。`properties` 是開放的袋子，需要時再加，不改 schema |
| 路徑一律相對於根、以 `/` 分隔 | 見 `graph_schema.md` › id 規則 |

---

## 不在這一層做的事

| 事情 | 在哪做 |
|---|---|
| 檢查路徑准不准讀 | ingest |
| 挑哪些副檔名去解析 | parse（registry 查不到就跳過） |
| 驗證邊的兩端節點都存在、算 `meta` | build |

---

## 未定之處

| 項目 | 缺什麼 |
|---|---|
| 樣式比對 | 目前只比對名字完全相符。`*.min.js`、`*.lock` 這類要靠樣式，尚未需要 |
| 讀專案自己的 `.gitignore` | 介面已預留（清單是參數），但沒有實作，也還沒決定要不要做 |
| 硬連結（hard link） | 與 symlink 不同，看起來就是一般檔案，會產生兩個節點指向同一份內容。目前不處理 |
