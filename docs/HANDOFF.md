# U9-CHT Handoff（2026-11-10）

給下一個工作階段（人或 AI Agent）的交接。
開工前仍須依 `AGENTS.md` 讀取 `AGENTS.md` 與 `ULTIMA_IX_CHT_MASTER_PLAN.md`。

---

## 1. 目前狀態一覽

- 分支：`p7-localization-pipeline`，未推送到 GitHub（遠端只有 `origin/main`）。
- 最新 commit：`133dfbc feat(session): --seed-saves and --keymap for continued test play`。
- 工作樹：乾淨。只有不可加入的未追蹤檔：`.vscode/`、`83e7052b…png`、`tools/u9xsb6bt2a*`、`tools/uixtools.zip`。
- 本機私人遊戲副本 `.local/runtime-game`：已還原成原版，沒有進行中的 session。
- 測試：`python -m unittest discover -s tests` → 161 tests OK（3 skipped）。
- Runtime：`U9ChtRuntime/0.2.19-p9-5`，建置在 `.local/p9-5/build/Release`。這輪不需要改 runtime。

### 翻譯進度（全部是 `draft`，尚未人工校稿）

| 資源 | 進度 | 遊戲內確認 |
| --- | --- | --- |
| 對話 text.flx | 7,368 / 7,390 | ✅ |
| 物品名稱 TYPENAME | 2,026 / 2,032 | ✅ |
| 書籍 BOOKS-EN | 391 / 451（60 筆刻意保留原文） | 只確認過 2 本 |
| 系統訊息 misctext.flx | 243 / 340（P10-1，本輪新增） | ❌ 尚未進遊戲 |
| 商店清單（BOOKS 內 56 筆） | 0 | ❌ 需研究 |

## 2. 本輪（P10-1）完成的事

1. **misctext.flx 支援**（commit `33e1201`）
   - 格式與 text.flx 相同：UTF-16LE、無 BOM、一個 NUL 結尾；348 slots，使用 340 個。
   - 用 `TextArchive` 重建與原檔逐位元組相同（BYTE-PERFECT，14,618 bytes）。
   - `MiscTextAdapter`；store 檔 `translation/zh-TW/misctext.jsonl`；`sources.json` 已加入基準雜湊 `3c5bb884…b570`。
   - runtime 方案放在 text domain，entry = `0xC000 + id`（`RUNTIME_CONTRACT["misc_entry_base"]`）。runtime 0.2.19 依字串內容比對，不需修改。和 text.flx 相同的譯文會共用方案（`shared_text_targets`）。
   - 刻意保留英文：力量之語音節（168–193）、咒語（276–311）、秘藥縮寫清單（316–347）。
   - 暫不翻：日誌目錄標題 `TABLE` / `of` / `CONTENTS`（22–24），要先看排版。
   - misctext 不套用 `譯名(English)` 標註規則（`ANNOTATION_EXEMPT_RESOURCES`）。
   - `resource-capabilities.json`：`unicode_runtime` 為 **HYPOTHESIS**。每個 UI 畫面都可能走不同的繪字路徑，要逐畫面在遊戲內確認後才能升級。
2. **石像鬼語原文移出 store**（commit `3e7033f`）
   - 書 40–45 的 `` `f5 `` 段落原本整段存在 `books.jsonl`。現在改存 `{{gargish:N}}` 佔位符，`pipeline.analyze()` 會從本機原文在記憶體中展開。
   - 重建出的 BOOKS-EN.FLX 與 P9-5 完全相同（`aec100af…ed03`）。
   - **待使用者決定**：這段原文仍在 3 個本機舊 commit 裡（`890d0ba`、`a98497f`、`2829a17`），尚未推送。要不要改寫本機歷史，由使用者決定，不要自行執行。
   - 更正：P9-5 報告寫「測試全部通過」有誤，當時防護測試 `test_tracked_store_contains_no_original_source_text` 其實失敗。
3. **書名**：不需要翻（STRONG EVIDENCE，靜態分析）。
   - 書本檔案物件 `[0x83D270]` 只有開檔 0x42E3C0、關檔 0x42E520、讀取 0x42E560 三處使用。讀取時只讀標題長度來跳過標題，標題位元組從未被讀入。
   - 標題只是開發者標籤（例如 `185: melvin`）。玩家看到的書名是內文第一行與物品名稱，兩者都已翻譯。
4. **測試工具**（commit `133dfbc`）
   - `run_p8_0_session.py` 新增兩個選項：
     - `--seed-saves DIR`（需搭配 `--preserve-saves`）：用上一場的存檔接續進度；
     - `--keymap FILE`：測試用按鍵檔以 `U9CHT-TEST.kmp` 名稱放入遊戲目錄，並經 `Options.ini` 選用；兩者在 finish 時還原，`Default.kmp` 不會被修改。
   - 本機作弊按鍵檔：`.local/p10-misc/keymap/U9CHT-TEST.kmp`。u9.exe 內有隱藏的 `Cheat Commands`：`fill_spellbook`、`recharge_mana`、`toggle_avatar_fast`／`fly`／`invulnerable`、`pass_one_hour` 等。**零售版是否停用：UNKNOWN。**
   - 按鍵說明：`docs/testing/KEYS_zh-TW.md`。

## 3. 下一步：遊戲內測試（等使用者說「準備好了」）

使用者的兩個存檔都還在吉普賽人馬車（開局建角）。目前的建置在 `.local/p10-misc/out`：

- pack `6f0d8850…bfbd`，10,028 個方案，2,724 個字形；
- misctext.flx `2e883335…7d7a`；
- 離線檢查用 jf-openhuninn 與 Noto 都 PASS。

啟動指令（使用者說「準備好了」之後才執行，不送任何自動輸入）：

```sh
python scripts/run_p8_0_session.py start --session .local/p10-misc/session-1 \
  --label "P10-1 misctext surfaces + cheat keys" --build .local/p10-misc/out \
  --runtime .local/p9-5/build/Release --config .local/p9-2/u9cht.ini --preserve-saves \
  --keymap .local/p10-misc/keymap/U9CHT-TEST.kmp --offline .local/p10-misc/off-huninn.jsonl
```

遊戲結束後**一定要**執行：

```sh
python scripts/run_p8_0_session.py finish --session .local/p10-misc/session-1
```

沒有 finish 的話，`.local/runtime-game` 會留著翻譯過的資源，本機測試會失敗。

新進度存檔會留在 `.local/p10-misc/session-1/final-savegame`。下一場加 `--seed-saves .local/p10-misc/session-1/final-savegame` 就能接著玩。

### 這場要檢查的項目

1. Esc 主選單、Ctrl+O 選項、Ctrl+S／L 存讀檔、Ctrl+Z 屬性、Ctrl+T 歷史、Ctrl+B 圖鑑。
2. Ctrl+Shift+1（`fill_spellbook`）有沒有作用。有作用的話接著看法術書：S、0–9、Ctrl+R、Ctrl+G。
3. 地球家裡的長篇書：鍵盤指令（BOOKS 183）、地球教學書（181/182）。
4. 時間允許的話推進到 Britannia 找商店，並存檔。
5. 結束後分析 `runtime.jsonl`：
   - 每個 misctext 方案的 wide 命中次數；
   - `flow_text` 事件裡有沒有商店字串（用來判斷商店畫面是否走 flow init 0x5C7620）。

### 判讀方式

- **畫面變中文**：該畫面走 constructor 0x615A10 → 0x615B7C 的轉換和既有的繪字 hook，可以升級為 CONFIRMED。
- **出現方框、`?` 或空白**：該畫面用了別的繪字路徑，要另外研究。必要時用 `--only` 把該畫面的字串排除在 build 之外。

## 4. 之後的待辦

- 寫 `reports/P10_1_MISCTEXT.md`（遊戲內結果出來後再寫；capabilities 已引用這個檔名）。
- 商店清單：格式是 `店名` + `#類型 "名稱" $價格`。範本註解說名稱長度有限。可能的做法是比照日誌的 ASCII 標記橋接，前提是確認走 flow init。
- 其他：
  - 避頭點（行首標點）規則；
  - 英文單字中途斷行；
  - 字型設定擴充；
  - 用 ✕ 關窗時的 0xC000041D 與原版比對；
  - 人工校稿；
  - IB-1 滑鼠移過顯示名稱（需使用者授權）。

## 5. 固定規則（使用者偏好）

- 一律用繁體中文回覆。
- 每次啟動遊戲前，先請使用者說「準備好了」。不送自動輸入。使用者會用遊戲內選單離開遊戲。
- 不提交遊戲原文、字型、本機絕對路徑。含英文原文的 workset 只放在 `.local/`。
- 本機翻譯工作檔：
  - `.local/translation-work/p10-misc/`（`m01.py`、`apply.py`、`run.sh`）
  - `.local/translation-work/p9-books/`
- commit 結尾加上：`Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`。
