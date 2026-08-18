---
description: "AX Followup — 管理「尾巴待辦」：任務結尾累積但還沒做的小事與建議。可列未清、標記完成、或手動補一筆。觸發語：「收不乾淨」「尾巴待辦」「還差什麼沒清」「有什麼沒收」「列 followup」「followup done/add」。適合收尾時盤點還差什麼沒收乾淨。"
argument-hint: "（空）列出未清 | done <關鍵字> 標記清除 | add <優先級> <內容> 手動加"
---

# ax:followup — 尾巴待辦管家

## 🔍 Recall（僅在遇到技術問題時）
本技能是輕量進度操作，一般**不需** recall。**只有**過程中冒出技術決策或不確定點時，才 `ax:recall "<關鍵字>"`（此時 recall 為輔助：查無≠沒做過）。

待辦尾巴存放：followups 目錄（`${AX_FOLLOWUP_DIR:-$HOME/.ax/followups}`，未設 env 用預設）下的 `followups.md`（未清）+ `archive/`（已清歸檔）。用前 `mkdir -p`。

> **首次執行告知**：若 followups 目錄不存在（首次使用），建立後在回報末尾附一行 `[AX] 首次執行：followups 目錄已建於 <實際路徑>（要改路徑：在 ~/.claude/settings.json 的 env 設 AX_FOLLOWUP_DIR）`。之後靜默。

## 輸出格式（重要）

**所有輸出一律用 Markdown table 呈現，不要用條列（bullet list）方式輸出。** 列出未清、`done` 清除回報、`add` 新增回報全部都要用表格。即使只有一筆也用表格。

依 `$ARGUMENTS` 決定動作：

## 無參數 → 列出未清（管家報告）

1. 讀 followups 目錄下 `followups.md` 的「## 未清」區
2. 產出一張表（依優先級排序 P0→FYI）：

   | # | 優先級 | 日期 | 來源 | 內容 | 建議下一步 |
   |---|--------|------|------|------|-----------|

3. 結尾提示：超過 7 天還沒清的標 ⚠️、總筆數、可用 `ax:followup done <關鍵字>` 清除

## `done <關鍵字>` → 標記清除

1. 在 followups.md 找到符合 `<關鍵字>` 的未清項（多筆匹配先列出問哪一筆）
2. 從「## 未清」移除該行
3. 追加到 followups 目錄下 `archive/{YYYY-MM}.md`，格式：`- [x] {原內容} （清除於 {今天日期}）`
4. 回報用 table：一欄「清掉的項目」、一欄「剩餘未清筆數」

## `add <優先級> <內容>` → 手動加一筆

1. append 到 followups.md「## 未清」：`- [ ] {優先級} ({今天日期}, 手動) {內容}`
2. 若優先級是 P0/P1/P2 → 額外推一份到提醒清單（可用 AX_REMINDER_LIST 指定，預設系統提醒）（見下方）
3. 回報用 table：顯示剛新增的那筆（優先級／日期／來源／內容）

## 自動擷取（任務結尾，非本指令觸發）

任務結尾若產出「尾巴待辦 / 建議」，**自動 append** 到 followups.md「## 未清」，格式同上，來源標該任務（如 `/收`、`/mission`、`/dw-audit`）。判優先級：線上事故→P0、今天要做→P1、其他依緊急度。

## P0-P2 推提醒清單（可用 AX_REMINDER_LIST 指定，預設系統提醒）（手機可見）

高優先項額外建一筆 Reminder（用 EventKit API 直接建立，不用 osascript 批次以免逐筆彈權限對話框；目標清單可透過 AX_REMINDER_LIST env 設定，未設則不指定 calendar，由 EventKit 用系統預設清單）：

```bash
python3 - << 'PY'
import os
from EventKit import EKEventStore, EKReminder, EKEntityTypeReminder
import Foundation
s=EKEventStore.new(); done={}
def cb(g,e): done['g']=g
s.requestAccessToEntityType_completion_(EKEntityTypeReminder, cb)
Foundation.NSRunLoop.currentRunLoop().runUntilDate_(Foundation.NSDate.dateWithTimeIntervalSinceNow_(3))
want=os.environ.get("AX_REMINDER_LIST")  # 未設 → 用系統預設清單
cal=None
if want:
    for c in s.calendarsForEntityType_(EKEntityTypeReminder):
        if c.title()==want: cal=c; break
if cal is None:
    cal=s.defaultCalendarForNewReminders()  # 系統預設提醒清單
r=EKReminder.reminderWithEventStore_(s); r.setTitle_("待辦尾巴：<內容>"); r.setCalendar_(cal)
s.saveReminder_commit_error_(r, True, None)
print("已推提醒（清單：%s）" % (cal.title() if cal else "系統預設"))
PY
```

## 安全閥
- 不刪 followups.md 既有未清項（只移到 archive）
- 標記清除前若關鍵字匹配多筆，先問清楚是哪一筆
- archive 只追加不覆蓋
