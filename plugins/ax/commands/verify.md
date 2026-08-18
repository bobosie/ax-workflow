---
name: verify
description: 實作後的實證：查「驗證程序目錄」(vox-trace CATALOG/specs)，命中就照步驟驗——A(真瀏覽器走A)優先、A被擋才 fallback B(live-API等效)，逐斷言判定。解決「實證摸不著頭緒」、讓使用者不用手動重測。只對「有可驗證產出」的改動觸發。
---

# ax:verify — 驗證程序目錄驅動的實證（A 優先 / B fallback）

實作（修 bug / 優化 / 新功能）完成後、交付前的實證。核心：不從零想「怎麼驗」——查累積的「這功能人怎麼驗過」照走。

## Step 0　觸發判準（先過這關，避免對 trivial 過度觸發）
**只有「有可驗證產出」的改動才跑本流程**——即 (a) 有 UI 入口，或 (b) 有可觀測業務結果（API 契約/DB 值/檔案產物/計算數值）。
**排除（不觸發，對齊 mission 簡單層 0-agent 精神）**：純文案/設定/註解、無行為變更的純重構、純 test-file 改動、一句話能答的快速操作、純唯讀調查/排查。屬這些 → 直接跳過本流程。

## Step 1　查目錄（在相關集合內窮舉，但集合有界）
- 權威來源：`${VOX_TRACE_DIR:-$HOME/vox-trace}/spec-schema/specs/**/*.yaml`（`assertions`/`endpoint` 在此；`feature`/`domain` 只有精修過的 spec 有、auto 骨架只有 `tags`——**主路徑是 grep endpoint/畫面關鍵字**，別依賴 feature/domain 普遍存在）；`CATALOG.md` 是人讀索引（不存在或過舊 → `cd ${VOX_TRACE_DIR:-$HOME/vox-trace} && npx tsx src/generate-index.ts` 生）。vox-trace clone 在別處 → 在 `settings.json` 的 `env` 設 `VOX_TRACE_DIR`（重開 session 生效）；目錄不存在 → 走 Step 5 提示補錄，別假裝查過。
- **相關性判準（不是關鍵字命中）**：一個程序「相關」= 它的 `assertions` 實際觸及本次改動的 **endpoint / 畫面 / 欄位**。共用步驟（`_shared/*.step.yaml`，如 login）**只在它本身就是被改的對象時才驗**，不因被別的程序引用就跟著全驗。
  - grep 定位：`grep -rlE "<改動的 endpoint 或畫面關鍵字>" ${VOX_TRACE_DIR:-$HOME/vox-trace}/spec-schema/specs/`，再逐檔看 assertions 是否真觸及。
  - 併 `memsearch search "<功能>"` 補語意（handbook/lessons）。
- **上限與溢出**：選出「直接覆蓋本次改動」的程序；若 >5 個 → 跑**最貼近改動的 top-3~5**，其餘列進報告交 lead/使用者決定是否加驗（對齊 mission「verifier 上限 3、超出列報告」）。**「不抽樣」限定在已選集合內逐一驗**（選集合可有上限、選中的不跳過）。

## Step 2　讀程序
命中程序 → 讀 `spec.yaml` 的 acts 或 `_shared/*.step.yaml`（path 照 CATALOG，相對 `spec-schema/`），取 `steps` + `assertions` + `*_e2e_helper`（有值＝有確定性 helper 可呼叫）。

## Step 3　執行——A 優先，A 被擋才 B（且寫明為何 fallback）
**A. 真瀏覽器走 A（首選；UI/視覺/互動類只能走 A）**
- 寫/跑 Playwright **腳本**（`import { chromium } from '<VOX_TRACE_DIR>/node_modules/playwright'`——JS import **不吃 shell 變數**，寫腳本時填 `${VOX_TRACE_DIR:-$HOME/vox-trace}` 展開後的絕對路徑；`npx tsx`；**不需 MCP**）驅動真瀏覽器照 `steps` 點過、`page.screenshot`，lead 用 `Read` 讀截圖 + 逐 `assertion` 判 pass/fail，`page.on('response')` 收 API 佐證。
- **Cloudflare 保護的 SPA 站點別自己 launch 冷 Chrome**（冷快取→chunk 冷發 503→前端框架不 mount）。**改連本機常駐暖 Chrome**（若你有；沒有就照常 launch）：`WS=$(curl -s http://127.0.0.1:${AX_CHROME_CDP_PORT:-9223}/json/version|python3 -c 'import json,sys;print(json.load(sys.stdin)["webSocketDebuggerUrl"])')` → `chromium.connectOverCDP(WS,{timeout:60000})`（直接給 ws URL；給 http 會 timeout）→ `ctx.newPage()`（開新分頁別動既有 tab）→ goto、判定、`page.close()`+`browser.close()`（只斷 CDP 不殺 Chrome）。暖 profile 有快取+cf_clearance 故正常 render。坑：暖 profile 可能有過期 token 彈 modal 蓋住按鈕 → 先 `button:has-text("關閉"),.el-dialog__headerbtn` 關掉。
  > 暖 Chrome 的 debug port 預設 `9223`，不同就設 `AX_CHROME_CDP_PORT`；`curl` 那行不通＝沒有常駐暖 Chrome，直接 `chromium.launch()` 即可。（此法對 CF 保護的內部管理後台實測可行：暖 profile 帶著 cf_clearance，冷 launch 則會卡在 503。）

**B. live-API 等效（僅當 A 被擋：站點 503 冷載節流 / 過不了 CF / captcha / 純後端無 UI）**
- 打 UI 呼叫的**同一支 live API** 判定（等效 verified，見 [[arsapi-local-test-env-and-live-api-verify]]）。**報告必寫明「為何走 B 不走 A」**。

**headless / 無人值守分支（`claude -p` 或其他無人值守 agent，無 display、無法開瀏覽器）**
- 屬 UI/視覺類而 A 開不了、B 又不適用 → **不假裝驗過**：標「headless 受限未實證：需人類在場走 A」，並走可驗證指令（DB query / grep / repro 腳本）把輸出附報告 + 列出未經人類確認的 CRITICAL（對齊 mission headless 降級分支）。

## Step 4　判定紀律
- 4xx/5xx 看**最終狀態**：錄製常見「第一次輸錯（401 密碼錯 / 500 ORA 重複鍵）→ 改正後 200」是操作者雜訊、**不是 bug**，別亂喊。
- 技術上 200 仍要驗**業務結果對**（餘額/數值/畫面文字），非只看狀態碼。
- 沒親眼看它做對事＝未 verified，標明別假裝（防謊報三階梯）。

## Step 5　查無程序 → 提示補錄
目錄無相關程序 → 告訴使用者「此功能尚無累積驗證程序，建議錄一次（vox-trace record）」；之後即進目錄，越積越多、下次就查得到。**不卡住、不假裝驗過。**

## Step 6　出實證報告
逐 assertion：pass / fail + 證據（截圖路徑 / API 回應摘要）；標明用了 A 還是 B（B 註明原因）、headless 受限項；命中但因上限未驗的列出交 lead；未驗到的標紅。
