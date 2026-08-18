# ax-workflow marketplace（本地）

AX 前綴的個人工作流 skill 模擬，供組織導入 dogfood。**不動現有 `~/.claude*/commands/` 任何檔案**。

## 內容
plugin `ax` — 8 個指令（收→recap、收不乾淨→followup）：
- `ax:mission`（複雜開發任務引擎）`ax:spec`（開發前規格）`ax:recall`（查知識庫）`ax:recap`（收割教訓）
- `ax:stash` / `ax:resume`（暫存 / 恢復進度）`ax:followup`（尾巴待辦）`ax:debug`（用網頁錄影做手動 QA 測試）

## 路徑與設定（org 使用者必讀）

**第一次用不會問你路徑**——所有路徑走「慣例優先」：套用 `$HOME` 相對的可攜預設，直接可用、零設定。首次建立資料目錄時會回報一行存放位置，之後靜默。

只有在你要換位置時（換硬碟／外接碟／跨裝置同步／特定提醒清單）才需覆寫。**覆寫方式**：在 `~/.claude/settings.json` 的 `env` 區塊設對應變數，**重開 session** 生效：

```jsonc
// ~/.claude/settings.json
{ "env": { "AX_STASH_DIR": "/your/path/.stash" } }
```

| 變數 | 預設（免設定即用） | 何時要改 |
|------|-------------------|---------|
| `AX_STASH_DIR` | `$HOME/.ax/stash` | 想把暫存進度放別處（如與既有 `~/Projects/.stash` 慣例一致） |
| `AX_FOLLOWUP_DIR` | `$HOME/.ax/followups` | 想把尾巴待辦放別處 |
| `AX_REMINDER_LIST` | 系統預設提醒清單 | 想把 P0-P2 待辦推到指定的 Apple 提醒清單 |
| `VOX_TRACE_DIR` | `$HOME/vox-trace` | vox-trace（`ax:debug` 錄影、`ax:verify` 驗證程序目錄都依賴）clone 在別的位置 |
| `AX_CHROME_CDP_PORT` | `9223` | `ax:verify` 走 A（真瀏覽器）時要連的**本機常駐暖 Chrome** debug port；沒有常駐 Chrome 就不用理，會直接 launch |
| memory | Claude Code 標準位置（`${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/<cwd>/memory`） | **不用設**，自動正確 |

> 為什麼預設是 `$HOME/.ax/` 而非 `~/Projects/`：`~/Projects/` 是特定使用者的個人慣例，不是每個人都有；`$HOME/.ax/` 一定存在、自動建立、不依賴任何目錄慣例。多裝置/多帳號同步為個人選配（一般單裝置成員無需理會）。

## 安裝
```bash
claude plugin marketplace add bobosie/ax-workflow   # 直接吃 GitHub，不必先 clone
claude plugin install ax@ax-workflow --scope user
```
安裝後**下一個 session** 生效（skill 於 session start 載入）。

## 移除
```bash
claude plugin uninstall ax@ax-workflow
claude plugin marketplace remove ax-workflow
```
