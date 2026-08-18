---
description: "AX Debug — 用網頁錄影做手動 QA 測試（推薦 QA 人員）。開瀏覽器錄影＋螢幕操作＋語音＋操作 trace（screen recording），讓你手動操作或貼網址測，說「好了」自動收尾上傳。觸發語：「debug」「錄一下」「錄影」「錄測試」「screen record」「手動走查」「重現 bug 留證據」。適合 QA 手動走查、重現 bug 並留完整證據供事後解析／回報。"
argument-hint: "[要測的網址，可留空開空白頁]"
---

# AX Debug — 用網頁錄影做手動 QA 測試（只錄＋上傳，解析在 Studio）

## 🔍 Step 0 — 先 Recall（AX 全技能通則，最高優先）
動手前、或過程中一遇到**不確定／錯誤／卡關／要做技術決策**：**第一步先 `ax:recall "<關鍵字>"`**——查團隊知識庫（過往經驗／解法）＋ reference／playbook／SOP。命中就沿用或以它為基礎調整。
> ⚠️ recall 命中率約 60%@5：**「查無」≠「沒做過」**（知識庫本身可能就漏），recall 是**輔助參考、不是判斷有無先例的依據**。**「查遍」的定義＝memsearch top-5 ＋（涉本專案時）掃一次 `doc/lessons-learned/` ＋ 最多換 1 次關鍵字**；到此仍無就自己想，別無限 retry、也別因查無就斷定「首次遇到」。

包一層 [vox-trace](${VOX_TRACE_DIR:-$HOME/vox-trace})：開一個 Playwright 控制的瀏覽器讓使用者**手動操作**（可貼網址測），全程錄 **影片 + 麥克風語音 + trace + network + DOM 操作（user-actions）**。

**本機（跑 ax:debug 的裝置）只做兩件事：錄製 + 上傳 Google Drive。** 後續的關鍵影格抽取 / 語音轉寫 / spec 產出等**解析工作一律交給更 powerful 的 Studio 設備**——`--pm-mode` 會跳過本機重處理，raw 錄製 ship 給 Studio。**不要在本機做任何解析**（不跑 analyze / generate / parameterize / keyframes）。

**預設關截圖**：只靠影片供 Studio 端抽關鍵影格，本機不拍 periodic/load 截圖（vox-trace 新版無 `--screenshots` 旗標＝全關，連 `screenshots/` 目錄都不建）。

**收尾兩條路都通**：使用者在 Playwright Inspector 按 **Resume**，或跟你（agent）說「**done / 好了 / 關掉 / 收工**」→ 你執行 `./start.sh stop` 安全收尾（**絕不 kill 進程**，會丟失全部產出）。

> 觸發：`/ax:debug`（可帶網址）。這是**互動任務**，全程在對話層做，不要開 Workflow（background agent 無法開瀏覽器）。

---

## 執行步驟

### 1. 啟動前檢查：vox-trace 版本 + 上傳鏈就緒（**必做**）

clone 下來的 vox-trace 可能過舊、缺 `stop` / `--pm-mode` 等基本功能。**啟動錄製前先更新到預期版本並驗證功能存在**，否則收尾或上傳會失敗。

```bash
cd ${VOX_TRACE_DIR:-$HOME/vox-trace} || { echo "❌ vox-trace 未 clone 到 ${VOX_TRACE_DIR:-$HOME/vox-trace}"; exit 1; }

# (a) 更新到最新（工作區乾淨才 fast-forward pull）
git fetch --quiet origin
BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)
if [ "${BEHIND:-0}" -gt 0 ]; then
  if [ -z "$(git status --porcelain)" ]; then
    git pull --ff-only origin main && echo "✅ vox-trace 已更新（原落後 ${BEHIND} commit）"
  else
    echo "⚠️ vox-trace 落後 ${BEHIND} commit 但工作區有本地改動 → 請先處理再錄，否則功能可能不全"
  fi
else
  echo "✅ vox-trace 已是最新"
fi

# (b) 驗證必要功能存在（缺任一 → 版本不符預期，別硬錄）
grep -q "cmd_stop" start.sh && grep -q "pm-mode" start.sh \
  && echo "✅ 功能檢查：stop（安全收尾）+ pm-mode（只錄不解析）皆支援" \
  || { echo "❌ 此版 vox-trace 不支援 stop / pm-mode，請更新後再用"; exit 1; }

# (c) 上傳鏈就緒檢查（缺金鑰 → 錄得成但傳不上，先提醒使用者）
[ -f ~/.config/vox-pm/service-account.json ] \
  && echo "✅ GDrive service-account 金鑰就位" \
  || echo "⚠️ 缺 GDrive 金鑰（~/.config/vox-pm/service-account.json）→ 錄後無法自動上傳。請先跑 vox-trace/install-pm.sh 或向開發團隊索取金鑰。"
launchctl list 2>/dev/null | grep -q vox-pm-uploader \
  && echo "✅ PM 上傳 worker（com.voxtrace.vox-pm-uploader）已註冊" \
  || echo "⚠️ PM 上傳 worker 未載入 → 錄製不會自動 ship。部署：sed 's#__VOXTRACE_DEST__#'\"${VOX_TRACE_DIR:-\$HOME/vox-trace}\"'#g' ${VOX_TRACE_DIR:-$HOME/vox-trace}/pipeline-pm/com.voxtrace.vox-pm-uploader.plist > ~/Library/LaunchAgents/com.voxtrace.vox-pm-uploader.plist && launchctl load -w ~/Library/LaunchAgents/com.voxtrace.vox-pm-uploader.plist"
```

- 錄音依賴 **sox**（`brew install sox`）；本 skill **必須錄音**（使用者邊操作邊口述意圖），缺 sox 要先裝。
- `start.sh record` 會自檢 `node_modules` / Playwright Chromium，缺就自動裝（已裝則秒過）。
- 本機**不需要 ffmpeg / Whisper**——那些是關鍵影格 / 轉寫用，屬 Studio 的解析工作，`--pm-mode` 會跳過。

### 2. 背景啟動錄製（**一定要 background**，否則會卡住對話）

用 Bash 的 `run_in_background: true` 啟動 —— **錄影 + 錄音 + 全 Playwright 擷取（trace/network/DOM），截圖預設關，PM 模式（只錄不解析）**：

```bash
cd ${VOX_TRACE_DIR:-$HOME/vox-trace} && VOX_OUTPUT_DIR="$HOME/vox-pm-recordings" \
  ./start.sh record --pm-mode \
  --name debug-<簡短描述或時間戳> \
  [--base-url <使用者給的網址>] \
  [--load-storage <path>]
```

要點（**別多帶旗標**）：
- **不要加 `--no-audio`**——本 skill 必須錄音（麥克風錄口述意圖，供 Studio 轉寫）。
- **不要加 `--screenshots`**——截圖預設關就是要的行為，加了反而開啟。
- `--pm-mode`：只錄製、跳過本機重處理（keyframes/transcribe/correlate），raw 錄製交 Studio。
- `VOX_OUTPUT_DIR=$HOME/vox-pm-recordings`：錄到上傳佇列監看的目錄，launchd worker 每 120s 自動 ship 到 GDrive（穩定後才傳，不會傳到一半）。
- **使用者有給網址** → 加 `--base-url <url>`。**沒給** → 不加，開 `about:blank` 請使用者自己貼。
- **需要免登入**（目標站台已有登入 session）→ 加 `--load-storage <path>`（如 `~/<你的專案>/.auth/session.json`）。
- 記住這次的 `--name`（給收尾/驗產出用）。

啟動後告訴使用者：
> 瀏覽器開好了，開始手動操作 / 貼網址測，**邊做邊口述**你在做什麼、預期看到什麼（麥克風會錄，供開發團隊解析）。測完了跟我說「**done**」或「**好了**」，我幫你收尾＋上傳；或你自己在 Playwright Inspector 按 **Resume** 也可以。

### 3. 等待收尾訊號

- **使用者說 done/好了/關掉/收工** → 執行安全收尾：
  ```bash
  cd ${VOX_TRACE_DIR:-$HOME/vox-trace} && VOX_OUTPUT_DIR="$HOME/vox-pm-recordings" ./start.sh stop
  ```
  **`stop` 必須帶與 record 相同的 `VOX_OUTPUT_DIR`**——`.active-session` 指標寫在該目錄下；漏了會在 repo 的 `recordings/` 找不到而報「找不到進行中的錄製」（每次 Bash 是新 shell、env 不留存，務必同一行帶上）。不帶 session 名 → 自動讀該目錄的 `.active-session`；多個並行錄製時才指定 `./start.sh stop <name>`。收尾機制＝在 session 目錄放 `.stop-recording` sentinel，等同按 Resume。
- **使用者自己按了 Resume** → 錄製進程會自行結束，直接進步驟 4。

### 4. 確認收尾完成 + 驗產出落地 + 確認已入上傳佇列

等 record 背景進程結束（讀該 background task 的完成通知，或 `pgrep -f "record-manual-session"` 確認沒了），然後驗**產出確實落地**、且**進入上傳佇列**（不要只看 stop 送出就宣稱成功）：

```bash
SESS="$HOME/vox-pm-recordings/debug-<name>"
ls -la "$SESS"
# PM 模式應有：*.webm（影片）/ audio.wav（語音）/ network.json / user-actions.json / trace.zip / metadata.json
# 注意：PM 模式「不」產 keyframes/ 與 screenshots/（那是 Studio 的解析工作）

python3 -c "import json;d=json.load(open('$SESS/metadata.json'));print('endTime:',d.get('endTime'),'| pmMode:',d.get('pmMode'))"
# endTime 有值 = 收尾流程完整跑完；pmMode: True = 只錄不解析、待 ship

# 立即觸發上傳 worker（不等 120s 週期），拿到 verified 上傳結果
bash ${VOX_TRACE_DIR:-$HOME/vox-trace}/pipeline-pm/vox-pm-queue-worker.sh
tail -5 ~/vox-pm-queue/worker.log 2>/dev/null
ls ~/vox-pm-queue/done/ ~/vox-pm-queue/failed/ 2>/dev/null   # 在 done/ = 已上傳；在 failed/ = 上傳失敗

# 端到端確認 GDrive 真的收到（含 _complete.json 的 session）
cd ${VOX_TRACE_DIR:-$HOME/vox-trace} && { [ -f ~/.config/vox-pm/env ] && source ~/.config/vox-pm/env || echo "⚠️ 缺 ~/.config/vox-pm/env → 跳過，GDrive 端到端確認可能無法執行"; } \
  && uv run --quiet --with google-api-python-client --with google-auth-oauthlib --with google-auth \
     python3 pipeline-pm/vox-pm-gdrive.py list --folder VoiceTrace-PM-Intake | grep debug-<name>
```

回報使用者：錄製已存檔（endTime/pmMode 已確認）、**已上傳 GDrive 並在 intake 清單看到**（verified）。若 `failed/` 有檔 → 明確回報上傳未成、原因（缺金鑰 `~/.config/vox-pm/service-account.json` / 網路），以及要補的東西。**注意 SHIP_FILES 含 trace.zip，大 session 上傳需時間**（`vox-pm-ship` exit 75 = 網路錯誤留 pending 重試，非失敗）。

---

## 注意事項

- **本機不做解析**——不跑 `analyze` / `generate` / `parameterize` / keyframes / 轉寫。這些是 Studio 的工作，`--pm-mode` 已在本機跳過。若使用者要「把這次操作變成測試」，回覆：raw 錄製已上傳 GDrive，spec 產出由 Studio 端做。
- **必錄影 + 錄音**：影片供 Studio 抽關鍵影格，語音供轉寫意圖。啟動指令**不得**帶 `--no-audio`。
- **截圖預設關**：**不得**帶 `--screenshots`；vox-trace 新版無旗標＝load/periodic/final 全關。
- **收尾只走 `stop` 或 Resume**——記憶 `feedback_vox-trace-resume-required`：直接 kill 進程會丟失所有產出（trace/network/user-actions 都還沒 flush）。
- `stop` 的機制：在 session 目錄放 `.stop-recording` sentinel，錄製端 race 到它就走**正常存檔流程**（見 `src/shared/stop-signal.ts`），跟按 Resume 等價。
- **上傳鏈**：`--pm-mode` + `VOX_OUTPUT_DIR=~/vox-pm-recordings` → launchd `com.voxtrace.vox-pm-uploader`（每 120s）→ `pipeline-pm/vox-pm-ship` → GDrive Shared Drive（service account 免登入）。缺金鑰時 worker 會把該筆留在 `failed/`，補上金鑰後會重試。已驗證全鏈（2026-07-17 自測：record→worker→ship 7 檔→GDrive VoiceTrace-PM-Intake）。
- **Flutter/canvas 前台**無 DOM selector，DOM 錄製脆弱；一般 DOM 站台（Vue/React/Element 等後台）才可靠。影片＋語音仍完整可用。
- 完整能力（多 Tab、PM 模式、GDrive 回傳鏈、Studio 端解析）見 `${VOX_TRACE_DIR:-$HOME/vox-trace}/README.md`。
