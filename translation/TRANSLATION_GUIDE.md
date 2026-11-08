# 《創世紀九：羽化昇天》(Ultima IX: Ascension) 繁體中文翻譯規範

本檔是 U9 翻譯的**權威規範**，與譯名權威檔 `translation/glossary/U9_TERMS.csv` 搭配使用。
大量翻譯開始前，譯名與本規範的「待決事項」需先由專案負責人確認。

- 建立：P8-A（2026-11-08）。參考 U7《Translation_Guide.md》與 U8 權威檔 `authority.tsv`。
- 台灣發行官方副標題確認：**《羽化昇天》**（負責人提供，2026-11-08）。
- 證據等級沿用 AGENTS.md §7：CONFIRMED／STRONG EVIDENCE／HYPOTHESIS／UNKNOWN。

---

## 1. 權威順序

譯名衝突時，依序採用：

1. 台灣官方中文版譯名（手冊或合法舊版資料）。**目前尚未找到 U9 中文手冊**，找到後補入並優先採用。
2. 本專案系列譯名：**U8 權威檔優先於 U7**（負責人決定，2026-11-08）。
3. 本檔與 `U9_TERMS.csv` 已核准（`approved`／`keep`）的譯名。
4. 英文原文語義。
5. 社群翻譯參考。

U7／U8 的譯名是本系列專案自訂的，不得標示為「官方譯名」。

---

## 2. 譯名權威檔（`U9_TERMS.csv`）

### 2.1 欄位

| 欄位 | 意思 |
| --- | --- |
| `source` | 英文原文，大小寫須與遊戲一致 |
| `target` | 唯一譯名 |
| `category` | `person` 人物、`place` 地點、`organization` 組織／族群、`title` 稱號、`virtue` 美德與原則、`spell` 法術、`monster` 生物、`item` 物品、`UI`、`system`、`other` |
| `status` | 見 2.2 |
| `enforcement` | `mandatory`：沒用到譯名就報錯；`recommended`：警告；`informational`：只提示 |
| `count` | 在遊戲文字中出現的次數（工具更新） |
| `example` | 一個出現位置，例如 `text.flx:4033`、`TYPENAME.FLX:5290`（工具更新） |
| `reference` | 譯名來源，例如 `U8 authority.tsv (approved)`、`P8-A candidate scan` |
| `notes` | 備註；與 U8 不同時，工具會在這裡記下 `U8 approved: …` |
| `annotate` | 加註英文的方式：`always`、`first`、`never`；空白表示依分類預設（見 4.7） |

### 2.2 狀態

與 U8 權威檔相同：

| status | 意思 | `target` |
| --- | --- | --- |
| `todo` | 尚未決定 | 可空白 |
| `proposed` | 建議譯名，尚未確定 | 必填 |
| `approved` | 定案，所有譯文都要使用 | 必填 |
| `keep` | 定案：保留英文 | 必須等於 `source` |
| `ignore` | 不是專有名詞（句首大寫、選單用字、一般詞） | 可空白 |
| `blocked` | 不得使用的譯法（例如已淘汰的舊譯名） | 必填 |

- 只有負責人可以把詞改成 `approved` 或 `keep`。
- 已核准的譯名要修改時，須在 `notes` 說明原因（AGENTS.md §16）。
- 同一個英文只能有一個核准譯名；兩個英文也不能核准成同一個譯名（工具會擋）。
- 例外：同一個東西的不同寫法（大小寫、複數、`Scroll: Fireball`／`Fireball Scroll`、`Buc's Den`／`Buccaneer's Den`）可以共用譯名，
  但要在 `notes` 寫 `variant of <主要寫法>`。主要寫法本身必須已核准、譯名相同，且不能再是別人的變體。
  工具產生的 `reference` 為 `plural of <單數>` 的複數形也視為變體；若負責人為複數另訂譯名（例如 Gargoyles 石像鬼族），則各自獨立。

### 2.3 更新候選詞

```bash
# 從本機遊戲檔重新掃描（保留手動填寫的 target／status／category／notes）
python scripts/update_terms.py --game-dir <U9 遊戲目錄> --u8-authority <U8 authority.tsv> \
    --review .local/p8a/U9_TERMS_REVIEW.tsv
# 檢查權威檔是否需要更新（不寫檔）
python scripts/update_terms.py --game-dir <U9 遊戲目錄> --u8-authority <U8 authority.tsv> --check
```

- 也可用環境變數 `U9_GAME_DIR`、`U8_AUTHORITY`。路徑不要寫進版本庫。
- 候選詞來源：
  - 對話與書本中反覆出現（至少 3 次）且不在句首的大寫名詞。
  - `text.flx` 對話檔所在的地區與 NPC 檔名。
  - 所有物品查看名稱（`TYPENAME.FLX`）。
- 分類是猜測的，需人工確認。
- U8 已核准、保留英文的詞，以及 U8 的人名、地名、組織、生物、稱號建議譯名，會自動填成 `proposed`。U8 一般名詞的建議不帶入。
- 複數形（例如 Gargoyles）自成一列；單數已有譯名時，工具會填入同一譯名（中文不分單複數）。
- `--review` 產生的 `U9_TERMS_REVIEW.tsv` 附有每個詞的一句英文原句，供審閱用。它**只能放在 `.local/`，不得 commit**（含原文）。

### 2.4 譯文如何使用譯名

翻譯紀錄（`translation/zh-TW/*.jsonl`）的 `terms` 欄列出該句用到的專有名詞英文，例如 `["Avatar", "Britannia"]`。
`validate` 會檢查譯文是否用到核准譯名，並依 `enforcement` 回報。

---

## 3. 系列譯名（沿用 U8 與 U7 對齊，負責人已核准，2026-11-08）

| 英文 | 譯名 | 依據 |
| --- | --- | --- |
| Ascension | 羽化昇天 | 台灣發行官方副標題（負責人確認） |
| Avatar | 聖者 | U8 approved（U7 相同） |
| Guardian | 守護者 | U8 approved（U7 相同） |
| Lord British | 不列顛王 | U8 approved |
| Britannia | 不列顛尼亞 | U8 approved |
| Moongate | 月之門 | U8 approved（U7 相同） |
| Blackrock | 黑石 | U8 approved（U7 相同） |
| Empath Abbey | 共情修道院 | U7 權威檔對齊（負責人確認） |
| Armageddon | 末日決戰 | U7 權威檔對齊（負責人確認） |
| Fellowship | 友誼會 | U7 權威檔對齊 |
| Pagan | 佩根 | U8 proposed |
| Gargoyle | 石像鬼 | U8 proposed（U7 相同） |

美德與三原則以權威檔為準（負責人決定，2026-11-08）：

- 八大美德：誠實 Honesty、慈悲 Compassion、英勇 Valor、正義 Justice、犧牲 Sacrifice、
  榮譽 Honor、靈性 Spirituality、謙遜 Humility。
- 三原則：真理 Truth、愛 Love、勇氣 Courage。

完整清單以 `U9_TERMS.csv` 為準，本表只列代表性詞。

---

## 4. 文字規範

### 4.1 標點

- 一律使用全形標點：，。！？：；（）
- `...`：中文慣用 `……`，但 **CONFIRMED（P8 第一波）：目前 runtime 不支援 `…`（U+2026）與 `—`（U+2014）**，
  `validate` 會報 `runtime-unsupported-scalar`。在 runtime 擴充字元範圍之前（需另行授權），
  請改寫句子：用逗號、句號或驚嘆號表達停頓，不要用其他符號硬湊。英文約 190 句有 `...`。
- 句尾 `?` → `？`。選項與台詞都適用。
- 數字用半形阿拉伯數字（`3`、`100`）。

### 4.2 引號

- CONFIRMED：`text.flx` 的台詞、字幕與選項**沒有任何英文引號**。中文**不要**在整句外加「」（與 U7 不同）。
- 句中引用他人的話、書名、咒語時才使用「」，引號內再引用用『』。

### 4.3 中英混排

沿用 U7 第 4 條與 U8 的寫法：

- 保留英文的名稱，與中文之間各留一個半形空白，例如「我是 Elad，住在 Moonglow 的北邊。」
- 英文緊接全形標點或位於句首、句尾時，那一側不加空白。
- 只有 `keep` 的詞或尚未核准的名稱才留英文；已核准譯名的詞一律用中文。
- UNKNOWN：中英混排在 U9 runtime 的換行行為尚未量測。

### 4.4 星號動作描述

- 6 句台詞用 `*…*` 表示動作或聲音，例如 `*whistling*`。保留星號，翻譯星號內文字：`*吹口哨*`。

### 4.5 稱呼與語氣（負責人決定，2026-11-08）

英文以 `you` 為主（約 3,000 句），也有古語 `thee／thou／thy`（約 70 句）。中文用「你／妳／您」，不用「汝」：

| 稱呼 | 何時使用 |
| --- | --- |
| 你 | 對男性、性別不明或多人；NPC 對聖者說話通常用「你」 |
| 妳 | 對女性說話，例如聖者對女性 NPC |
| 您 | 對王族、尊長或表示敬意，例如對不列顛王；NPC 對聖者表示尊敬時也可用 |

- `thee／thou／thy` 照同樣規則譯成你／妳／您，用語氣與用詞表現古風，不改用「汝」。
- 同一個 NPC 對同一對象的稱呼要前後一致。
- `milord` → `大人`、`milady` → `女士`（U7）。

### 4.6 真言與咒語

- 八美德的真言（例如 Ahm、Mu、Summ、Om、Lum、Cah、Beh）與魔法咒語**保留英文**，用「」括住，例如「Ahm」（沿用 U7 第 2、6 條）。U9 文字中這類詞很少（各 1–2 句）。
- 單獨成一條的真言或咒語答案（例如聖壇的 `mu`、`vas mani corp`）**不翻譯，保持 `untranslated`**：
  HYPOTHESIS：遊戲可能拿這些條目比對玩家輸入，翻譯後可能無法過關。驗證前一律保留英文。

### 4.7 專有名詞加註英文（負責人決定，2026-11-08）

格式：中文譯名後緊接**半形**括號與英文，不留空白，例如 `艾蓮娜(Elaina)`、`不列顛尼亞(Britannia)`。

| `annotate` | 何時加註 | 分類預設 |
| --- | --- | --- |
| `always` | 每一句都加註 | `person`（一般 NPC 人名） |
| `first` | 每個對話檔裡第一個出現該詞的句子加註，其餘只寫中文 | `place`、`organization`、`title`、`spell`、`monster`、`other` |
| `never` | 不加註 | `virtue`、`item`、`UI`、`system` |

- 常駐角色與系列名詞改用 `first`，避免每句都加英文（已在權威檔標好）：
  - 系列名詞：Avatar 聖者、Lord British 不列顛王、Guardian 守護者。
  - 同伴：Iolo、Shamino、Dupre、Geoffrey、Jaana、Julia、Katrina、Mariah（負責人決定，2026-11-08）。
- 「每個對話檔」指 `text.flx` 裡同一個 `ConvoLib\地區\NPC` 原始檔的條目，以條目編號排序。玩家走不同分支時，可能先看到沒有加註的句子，這是已知的近似。書本與物品名稱則每一則各自計算。
- 只有已核准（`approved`）且譯成中文的詞需要加註；`keep` 的詞本來就是英文，不加註。
- `validate` 會檢查：該加註卻沒有加 → `annotation-missing`（依 `enforcement` 決定錯誤或警告）；`never` 的詞卻加了 → 警告；`first` 的詞在非第一句加了 → 提示。判斷「第一句」需要本機遊戲檔（`--game-dir`）。
- U8 的自動加註由引擎在執行時處理；U9 改為寫在譯文裡。若日後要做到依實際對話順序判斷，需要另外設計 runtime 功能。

---

## 5. 各資源的注意事項

| 資源 | 內容 | 規則 |
| --- | --- | --- |
| `text.flx` | 對話、字幕、玩家選項 | 純 UTF-16 文字，沒有控制碼與佔位符號（CONFIRMED）。英文中位數 61 字元，最長 535。**譯文不得超過 512 個 UTF-16 單位**（runtime 上限，超過會被拒絕）。選項要短，避免超出選單寬度。 |
| `TYPENAME.FLX` | 物品查看名稱 | 短名詞，不加標點。多個物品共用同一英文名稱時譯名須一致；相同譯文會共用一個 runtime 計畫。 |
| `BOOKS-EN.FLX` | 書本、告示 | **目前不能中文化**：中文書本儲存路徑尚未驗證。英文中的 `` `f0 ``–`` `f9 ``（字型）、`` `p ``（換頁）、換行必須原樣保留。`#數字`、`$數字` 的用途 UNKNOWN，一律保留。 |
| `misctext` | 介面文字 | 尚無工具支援，不在本階段範圍。 |
| `text.flx` 日誌條目 | 聖者的日誌 | CONFIRMED（P8 第一波實機）：日誌不經過目前的 runtime 繪字路徑，**中文不會顯示**，仍顯示英文。可以先翻譯（分類填 `journal`），但需另行授權研究日誌路徑後才會生效。 |

---

## 6. 待決事項（大量翻譯前需負責人確認）

| # | 事項 | 狀態 |
| --- | --- | --- |
| 1 | 系列譯名與權威檔 | **已核准**：負責人修訂後全部 `proposed` 改為 `approved`（768 個，2026-11-08） |
| 2 | 人名、地名的寫法 | **已決定**：中文譯名加註英文。一般 NPC 人名每句加註；地名與其他專有名詞每個對話檔第一次加註；聖者、不列顛王、守護者與同伴只在第一次加註（見 4.7） |
| 3 | 加註格式 | **已決定**：半形括號 `譯名(English)` |
| 4 | 稱呼 | **已決定**：你／妳／您，不用「汝」（見 4.5） |
| 5 | 美德與三原則譯名 | **已決定**：以權威檔為準；三原則為真理、愛、勇氣（見第 3 節） |
| 6 | 台灣官方副標題與手冊 | **副標題已確認**：官方發行譯為《羽化昇天》（負責人確認，2026-11-08）；手冊處理中，取得後再比對細部譯名 |
| 7 | 與 U7 權威檔對齊 | **已完成**：共情修道院、末日決戰、時間暫停、迷惑術、遙控術、隱身術等法術與核心聖物已對齊；U9 為樹狀對話系統，不套用 U7 關鍵字選單選項（負責人確認，2026-11-08） |
