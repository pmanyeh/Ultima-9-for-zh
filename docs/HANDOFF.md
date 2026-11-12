# U9-CHT Handoff（2026-11-11）

給下一個工作階段（人或 AI Agent）的交接。
開工前仍須依 `AGENTS.md` 讀取 `AGENTS.md` 與 `ULTIMA_IX_CHT_MASTER_PLAN.md`。

**手冊譯名校對已完成（2026-11-11，見第 4 節）。** 下一步：進遊戲確認（第 5 節），以及人工校稿。

---

## 1. 目前狀態一覽

- 分支：`p7-localization-pipeline`，已推送到 `origin/p7-localization-pipeline`（2026-11-11）。
- 推送前改寫了本機歷史（使用者決定，2026-11-11）：
  - 3 個舊 commit 的 `books.jsonl` 含石像鬼語原文，改成和 `89d9118` 相同的 `{{gargish:1}}` 佔位符；只替換那 6 段原文，其他內容不變。
  - 驗證：最終檔案樹和改寫前完全相同（`900d0fe5…`）；commit 數和訊息都不變；尚未推送的歷史中原文殘留為 0。
  - 從那 3 個 commit 起，之後所有 commit 的雜湊都改變了；本文件和 P10-1 報告已更新成新雜湊。
  - 改寫前的歷史只留在本機備份分支 `backup/p7-before-gargish-rewrite`，**不可推送**。確認不再需要後可以刪除。
- 工作樹：只有不可加入的未追蹤檔：`.vscode/`、`83e7052b…png`、`tools/u9xsb6bt2a*`、`tools/uixtools.zip`。
- 本機私人遊戲副本 `.local/runtime-game`：已還原成原版，沒有進行中的 session。
- 測試：
  - `python -m unittest discover -s tests` → 166 tests OK（3 skipped）；
  - C++ 在 `.local/p10-misc/build` 執行 `ctest -C Release` → 9/9。
- Runtime：`U9ChtRuntime/0.2.31-p11`，建置在 `.local/p10-misc/build/Release`。
- 最新完整建置：`.local/p10-misc/out-m12`（含 `runtime/movies.tsv`），結果 PASS（errors=0）。

### 翻譯進度（全部是機器初稿 `draft`，尚未人工校稿）

| 資源 | store 檔 | 筆數 | 遊戲內確認 |
| --- | --- | --- | --- |
| 對話 text.flx | `text.jsonl` | 7,368 / 7,390 | ✅ |
| 物品名稱 TYPENAME | `typename.jsonl` | 2,026 / 2,032 | ✅ |
| 書籍 BOOKS-EN（含 56 個商店檔） | `books.jsonl` | 447 | 書本與路牌 ✅；商店清單 ❌ 未測 |
| 系統訊息 misctext.flx | `misctext.jsonl` | 242 / 340（刻意保留的英文見 3a） | 主要 UI ✅ |
| 影片字幕 | `movies.jsonl` | 42（draft 34、review 8） | 檢視工具 ✅；遊戲內 ✅（開場動畫，session 17；Esc 跳過 session 24） |
| 時鐘訊息（u9.exe 內的句型） | `runtime/U9ChtRuntime/clock_text.h` | 規則式改寫 | ✅ 遊戲內確認（2026-11-12） |

譯名權威檔 `translation/glossary/U9_TERMS.csv`：1,457 筆，其中 approved 768、todo 669、ignore 20。

## 2. 固定規則（使用者偏好）

- 一律用繁體中文回覆，包括工具呼叫之間的短訊息。
- 每次啟動遊戲前，先請使用者說「準備好了」。不送自動輸入。使用者會用遊戲內選單離開遊戲。
- 遊戲結束後一定要執行 `finish`，執行前先確認 `u9.exe` 已經結束。未經同意不可強制關閉遊戲。
- 不提交遊戲原文、字型、本機絕對路徑、英文原文。含英文原文的 workset 和語音辨識稿只放在 `.local/`。
- commit 結尾加上：`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`。
- 新的 hook 或 renderer 工作需要使用者明確授權（AGENTS §13、§14）。

## 3. 已完成的工作（P10～P11）

### 3a. P10-1 misctext UI（報告：`reports/P10_1_MISCTEXT.md`；研究：`docs/research/U9_MISCTEXT_UI_PATH.md`）

- 做法 M1：misctext 字串前面加 4 bytes 標記（`0x8F` 加 3 位 base-94 數字）。在排版 0x5C7620、繪字 0x5C5C00、訊息容器複製 0x41BC61 三處就地移除。
- 遊戲內已確認：選項頁、目錄、主選單按鈕、離開遊戲對話框（內縮 8 px）、圖鑑、路牌（亮字加黑框）。
- 刻意保留英文：
  - 力量之語音節（168–193）、咒語（276–311）、秘藥縮寫（316–347）；
  - 日誌目錄的 `TABLE of CONTENTS`；
  - 圖鑑花體字標題（misctext 255）。
- 使用者審閱過的翻譯：BOOKS 1 的標題改為「怪獸／敵人」。

### 3b. P10-2（小字型、時鐘已在 2026-11-12 進遊戲確認；商店尚未）

- 小字型中文縮放（`38a5916`）：字型高度 15–16 用 14 px，≤14 用 12 px。只套用在 misctext UI，日誌、書頁、路牌維持 16 px。
- 商店清單（`4c52ab4`）：商品名稱取 TYPENAME 譯文；店名方案 0xE000 起；runtime 在每個商品名前插入標記。
- 時鐘訊息（`678e474`）：在 0x41BC61 比對英文句型，改寫成中文；單字方案 0xF000 起。

### 3c. P11 影片字幕（研究：`docs/research/U9_MOVIE_SUBTITLES.md`）

- 12 部影片，只有 4 部有對白：intro、samhayne、raven、ambush。其他 8 部經過關閉 VAD 的整片辨識和 15 秒分段強制辨識，都沒有對白；兩個單字候選由使用者聽過確認不是對白。
- 做法 B'（`6494cff`）：runtime 攔截 `CoCreateInstance`（IAT 0x740418）的 FilterGraph，改用自己的播放器播放，以 pl_mpeg（MIT）解碼，用 GDI 畫字幕。GOG 的 `dshow.dll` 不修改。
  - 只有建置輸出裡有 `runtime/movies.tsv` 時才啟用。
- 字幕語言：**只放中文**。使用者在 2026-11-11 決定不做中英並呈，因為英文對白散布有版權問題。
- 檢視工具：`python scripts/movie_review.py <movie> [--scale 2]`。按鍵：空白鍵暫停、←/→ ±5 秒、↑/↓ ±1 秒、PgUp/PgDn 上下一句、R 重新載入。
  - 修改 `movies.jsonl` 後執行 `--cues-only`，再在工具裡按 R。
- 語音辨識的教訓：VAD 會濾掉壓在配樂下的對白（intro 2:14–2:40 整段遺失）。之後一律關閉 VAD，並逐字檢查字幕是否涵蓋每個辨識出的字。
- 本機工具（僅本機）：
  - FFmpeg 9.0.2（winget gyan）；
  - faster-whisper 1.2.1，裝在 `.local/tools/asr-venv`；
  - 辨識稿放在 `.local/movie-asr/`。

### 3d. 影片修正與滑鼠功能（2026-11-11）

- 影片（`5ddc86d`）：
  - 影片視窗蓋滿遊戲畫面；字幕改用快取點陣圖，播放不再延遲。
  - 月之門的開場動畫播放完整（session 17）。
  - Esc 跳過還沒再測。
- 滑鼠功能（IB-1／IB-2，runtime 0.2.40，見 `docs/IMPROVEMENT_BACKLOG.md`）：
  - 游標停留 250 ms 顯示物品名稱。
  - 滾輪翻頁；Ctrl＋滾輪縮放鏡頭。
  - 已修正 Ctrl+X 誤觸離開確認。
  - session 23 遊戲內全部 PASS。
- 堆疊物品名稱「(27) 金幣」（`edbf99f`，runtime 0.2.41）：
  - 遊戲用 `"(%d) %s"` 組標籤，前綴會讓標記比對失敗；
  - 現在允許數量前綴；
  - session 25 PASS。
- 影片 Esc 跳過：session 24 PASS（1.96 秒時由遊戲的按鍵處理停止）。
- 旁白字幕在某些視角消失：只記錄、不修改。證據強，是原版行為，見 `docs/research/U9_NARRATION_CAMERA_VISIBILITY.md`。
- session 24 的「閃退」其實是視窗被最小化，遊戲仍在執行；原因不明，可能是焦點被搶走。
- 啟動頁 `U9Cht.exe`（`3ae3b5f`，runtime 0.2.42，說明見 `runtime/U9ChtFront/README.md`）：
  - 頁面內容：遊戲位置、強化功能開關、字型與日誌排版、解析度。
  - 開始遊戲時套用中文化資料，離開後還原。
  - 解析度只支援 800×600 和 1600×1200，其他大小會讓 runtime 以錯誤 18 結束遊戲。
  - 測試資料夾：`.local/p10-misc/front-release`，遊戲位置指向私人副本。
  - **測試時不要按「自動搜尋」**：它會找到使用者原本的 GOG 安裝。
- Steam 版支援（runtime 0.2.43）：
  - Steam 版 `u9.exe` 就是 GOG 版加上 EA 數位簽章；程式碼、`ddraw.dll`、4 個 FLX 都相同（CONFIRMED）。
  - 啟動器和 runtime 接受兩種雜湊值。
  - 自動搜尋會讀 Steam 遊戲庫（`libraryfolders.vdf`）；同時找到 GOG 和 Steam 版時，由玩家用「切換版本」按鈕選擇。
  - Steam 版的 `dxcfg.ini` 是 `display=desktop`，改解析度時不動它。
  - 私人副本 `.local/steam-game` 已在遊戲內實測，中文化正常（2026-11-12）。
  - **測試時也不要按「切換版本」**：它會指到使用者原本的安裝。
- 「讀檔後再開新遊戲，世界沒有重置」：原版 bug，英文原版也會（CONFIRMED）。只記錄，見 `docs/research/U9_NEW_GAME_AFTER_LOAD.md`。說明檔要提醒玩家先重新啟動遊戲。
- 目前最新建置是 `out-m24`，存檔在 `.local/p10-misc/session-27/final-savegame`。

## 4. 用中文手冊校對文本（2026-11-11 完成）

### 4.0 結果

- 手冊三冊（Journal、魔法書、安裝指引）逐頁讀完。比對 241 個詞：一致 80、衝突 123、權威檔沒有 38。
- 使用者逐項裁決（原則與例外見翻譯規範 §1.1）。權威檔改 188 列、新增 35 列；store 改 1,639 筆（text 1,203、TYPENAME 185、BOOKS 173、misctext 72、影片 6），另外 6 筆因譯名變長重新斷行。
- 驗證：
  - validate PASS（error 0）；
  - `python -m unittest discover -s tests` → 166 OK（3 skipped）；
  - 完整建置 `.local/p10-misc/out-m13` PASS（含 `runtime/movies.tsv`）；
  - C++ 沒有變動，未重跑 ctest。
- 本機工作檔（不可提交）在 `.local/manual/`：
  - 逐頁筆記 `manual_terms_notes.md`；
  - 裁決表 `DECISIONS.csv`、`MISSING.csv`；
  - 套用腳本 `apply.py`、`glossary_update.py`；
  - 修改前後對照 `apply/diff.jsonl`。
- 手冊掃描檔不在 repo 裡，也沒有複製進 `.local/`；位置問使用者。
- 遊戲內待確認：
  - 法術書的儀式清單：標籤變長，例如「重聚肉體與靈魂儀式」9 個字，要看會不會超出。
  - 狀態頁：例如「長程武器」。

以下是校對前的原始計畫，保留作紀錄。

使用者已取得當初台灣發行的中文手冊。依 `translation/TRANSLATION_GUIDE.md` §1，它是**第 1 順位權威**，高於 U8／U7 系列譯名。

### 4.1 手冊的處理規則（AGENTS §17）

- 手冊掃描檔、照片、OCR 全文**只放在本機**，例如 `.local/manual/`（已在 `.gitignore` 涵蓋的 `.local/` 下）。不可提交。
- repo 只能放：
  - 核准的譯名；
  - 出處位置註記，例如「手冊 p.12」；
  - 簡短的事實引用。
- 從手冊採用的譯名，要在 `U9_TERMS.csv` 的 notes 註明出處頁碼。之後可以標成「官方譯名」，這是唯一可以這樣標示的來源。

### 4.2 建議流程

1. **整理手冊譯名**：列出手冊中的人名、地名、美德、咒語、秘藥、物品、職業、介面用語，和 `U9_TERMS.csv` 比對，分成三類：一致、衝突、權威檔沒有。
2. **衝突交給使用者決定**：手冊譯名和已核准的 U8／U7 譯名不同時，不可自行替換。整理成表請使用者裁決，因為這會影響全部 store。
3. **更新權威檔**：`python scripts/update_terms.py`（用法見翻譯規範 §2.3）。
4. **找出受影響的譯文**：用 `grep` 搜尋 store 中的舊譯名，列出受影響的筆數與 key。
5. **改譯文**：
   - 匯出 workset：`python scripts/export_translation_workset.py --resource <資源> --existing-only --output .local/translation-work/<名稱>.jsonl`（含英文原文，只能放 `.local/`）；
   - 修改 target；
   - 匯入：`python scripts/import_translation_workset.py --game-dir .local/runtime-game <workset>`。可先加 `--dry-run` 預覽。
   - 注意：匯入前要確定 store 自匯出後沒有被改過，否則會衝突，要重新匯出。
6. **驗證**：
   - `python scripts/validate_translation.py`；
   - `python -m unittest discover -s tests`；
   - 完整建置 `python scripts/build_localization.py --game-dir .local/runtime-game --font .local/p5-highres/font/NotoSansCJKtc-Regular.otf --output .local/p10-misc/out-m13`。
7. **狀態**：使用者校對通過的條目才改為 `review` 或 `approved`。不可覆寫 `approved` 的譯文而不說明理由（AGENTS §16）。

### 4.3 校對時要注意

- 專有名詞加註英文的規則（翻譯規範 §4.7）：
  - 一般 NPC 人名每句都加註；
  - 地名與其他專有名詞，在每個對話檔第一次出現時加註；
  - 聖者、不列顛王、守護者與同伴只在第一次加註；
  - misctext 不加註。
- 保留控制碼、`%s`、換行、`{{gargish:N}}` 佔位符（AGENTS §18）。validate 會檢查。
- 影片字幕 `movies.jsonl` 裡有 8 句是 `review`。例如「黑暗之鏡」不在權威檔裡；如果手冊有這個詞，就以手冊為準。

## 5. 尚未進遊戲測試的項目（需要使用者說「準備好了」）

建置改用手冊校對後的 `out-m13`。

```sh
python scripts/run_p8_0_session.py start --session .local/p10-misc/session-12 \
  --label "P10-2/P11 small em / shops / clock / movies / manual terms" --build .local/p10-misc/out-m13 \
  --runtime .local/p10-misc/build/Release --config .local/p9-2/u9cht.ini --preserve-saves \
  --seed-saves .local/p10-misc/session-1/final-savegame \
  --keymap .local/p10-misc/keymap/U9CHT-TEST.kmp
python scripts/run_p8_0_session.py finish --session .local/p10-misc/session-12
```

要檢查的項目：

- **影片**：開場動畫是否播放、字幕是否出現、會不會被 ddraw 轉接層蓋住、Esc 能否跳過、播完能否回到遊戲。在 snapshot 的 `movies{}` 計數裡確認。
- ~~小字型 UI、時鐘~~（2026-11-12 使用者確認 OK）；尚未確認：商店買／賣清單、存讀檔頁、法術書、屬性頁。
- 手冊譯名：
  - 法術書的儀式清單：例如「重聚肉體與靈魂儀式」，看標籤會不會超出。
  - 法術名稱：例如「地－召喚不死生物」。
  - 狀態頁的新用語：機敏、神力、長程武器、生命力。
- session 11 在播放影片時截圖，遊戲閃退（0xC0000005，原因 UNKNOWN，當時 runtime 閒置）。可以拿原版遊戲比對看看。

## 6. 其他待辦

- 啟動頁下一步：在玩家電腦上建置 `data/`。
  - 需要附帶 Python（embeddable 版）和 `u9cht` 套件，從玩家自己的遊戲檔建置。
  - 建置出的 FLX 含英文原文，不能散布。
- 發布打包流程：還沒規劃。
- 說明檔 `說明.txt`：要寫進「開新遊戲前請先重新啟動遊戲」（原版 bug）。

- 避頭點（行首標點）規則、英文單字中途斷行。
- 用 ✕ 關窗時的 0xC000041D 與原版比對。
- 商店清單 QA：還有 14 個物品和 7 個註解的加註警告（見 P10 文件）。
- 本機翻譯工作檔：`.local/translation-work/`（p10-misc、p10-shops、p9-books）。
