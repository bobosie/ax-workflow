#!/usr/bin/env bash
# AX 工作流 — 一鍵初始化（可重複執行：已裝則檢查+更新，不重裝、不重生金鑰）。
# 一般使用者只需執行這一行，最多輸入一次密碼。組織端點用 --server 帶入，套件本身不含任何組織設定。
set -euo pipefail
export LANG="${LANG:-en_US.UTF-8}" LC_ALL="${LC_ALL:-en_US.UTF-8}"

CENTRAL=""; NO_SCHEDULE=0; NO_PLUGIN=0; NO_DEPS=0
while [ $# -gt 0 ]; do case "$1" in
  --server) CENTRAL="$2"; shift 2;;      # 選填：中央 recall server URL（不給＝本機獨立模式）
  --no-schedule) NO_SCHEDULE=1; shift;;
  --no-plugin) NO_PLUGIN=1; shift;;
  --no-deps) NO_DEPS=1; shift;;
  *) shift;;
esac; done

PKG="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$PKG/../.." && pwd)"
PY="$(command -v python3 || true)"; OS="$(uname)"
VHOME="${AX_VAULT_HOME:-$HOME/.ax-vault}"; RUNTIME="$HOME/.ax-workflow/bin"
CFG="$HOME/.config/ax-workflow"; BIN="$HOME/.local/bin"
mkdir -p "$RUNTIME" "$CFG" "$BIN"
IS_UPDATE=0; [ -f "$CFG/env" ] && IS_UPDATE=1

say(){ printf '  %s\n' "$*"; }
[ "$IS_UPDATE" = 1 ] && echo "🔄 AX 工作流：偵測到已安裝，檢查更新中…" || echo "🚀 AX 工作流：首次安裝中…"

# 自我更新（可重複執行→拉最新版）
if [ "$IS_UPDATE" = 1 ] && git -C "$REPO" rev-parse >/dev/null 2>&1; then
  git -C "$REPO" pull --ff-only >/dev/null 2>&1 && say "已更新到最新版" || true
fi

# 依賴（缺才裝；mac=brew→靜態檔備援, linux=apt）。非工程師的 Mac 常無 brew，故 age 有 brew-free 靜態備援。
export PATH="$BIN:$PATH"
SUDO=""; [ "$(id -u)" = 0 ] || command -v sudo >/dev/null 2>&1 && [ "$(id -u)" != 0 ] && SUDO=sudo
ensure(){ command -v "$1" >/dev/null 2>&1 && return; say "安裝 $1…"
  if [ "$OS" = Darwin ]; then command -v brew >/dev/null 2>&1 && { brew install "$2" >/dev/null 2>&1 || brew install "$1" >/dev/null 2>&1; } || true
  else $SUDO apt-get update -qq >/dev/null 2>&1; $SUDO apt-get install -y -qq "$2" >/dev/null 2>&1 || true; fi; }
age_static(){ # 無 brew 時直接抓官方靜態 age（github release）
  a="$(uname -m)"; [ "$a" = x86_64 ] && a=amd64 || a=arm64; o=darwin; [ "$OS" != Darwin ] && o=linux
  curl -fsSL "https://github.com/FiloSottile/age/releases/download/v1.2.1/age-v1.2.1-$o-$a.tar.gz" -o /tmp/age.tgz 2>/dev/null \
    && tar xzf /tmp/age.tgz -C /tmp 2>/dev/null && cp /tmp/age/age /tmp/age/age-keygen "$BIN"/ && chmod +x "$BIN"/age* && rm -rf /tmp/age /tmp/age.tgz; }
if [ "$NO_DEPS" = 0 ]; then
  ensure age age
  command -v age >/dev/null 2>&1 || { say "age 改用靜態檔（無 brew）"; age_static || say "⚠ age 安裝失敗，請手動裝"; }
fi
[ -z "$PY" ] && PY="$(command -v python3 || echo /usr/bin/python3)"
AGE="$(command -v age || echo age)"

# runtime（每次刷新＝更新）
cp "$PKG"/runtime/* "$RUNTIME"/ 2>/dev/null || true; chmod +x "$RUNTIME"/vault 2>/dev/null || true

# 端點（不含任何組織字樣；預設本機獨立）
RECALL="${CENTRAL:-http://127.0.0.1:7654}"
CFGDIRS=""; for d in "$HOME"/.claude*; do [ -d "$d" ] && CFGDIRS="$CFGDIRS:$d"; done
cat > "$CFG/env" <<EOF
AX_RECALL_SERVER=$RECALL
AX_VAULT_HOME=$VHOME
AX_VAULT_AGE=$AGE
AX_VAULT_BIN=$RUNTIME/vault
AX_SCAN_BIN=$RUNTIME/scan_secrets.py
AX_SCAN_ROOTS=$HOME/Projects:$HOME/Tool:$HOME/.config${CFGDIRS}
AX_INDEX_GLOBS=$VHOME/index/*.md:$HOME/Projects/*/doc/lessons-learned/*.md
AX_SLACK_DM=${AX_SLACK_DM:-}
AX_SLACK_BOT_ENV=${AX_SLACK_BOT_ENV:-}
EOF

# shims
for t in vault ax_recall; do
  src="$RUNTIME/$t"; [ "$t" = ax_recall ] && src="$RUNTIME/ax_recall.py"
  printf '#!/usr/bin/env bash\nset -a; . "%s/env"; set +a\nexec "%s" "%s" "$@"\n' "$CFG" "$PY" "$src" > "$BIN/$t"
  chmod +x "$BIN/$t"
done

# 身分：只在不存在時生成（重複執行不重生）
set -a; . "$CFG/env"; set +a
if [ ! -f "$VHOME/identity/age.key" ]; then "$PY" "$RUNTIME/vault" init >/dev/null; say "已生成你的專屬金鑰"; else say "金鑰已存在，保留"; fi
PUB="$(cat "$VHOME/recipients/personal.txt" 2>/dev/null | head -1 || echo '?')"

# 排程（每日 09:15 自動歸檔）— mac=launchd / linux=cron
if [ "$NO_SCHEDULE" = 0 ]; then
  if [ "$OS" = Darwin ]; then
    LA="$HOME/Library/LaunchAgents"; mkdir -p "$LA"; PL="$LA/com.$(whoami).ax-autoscan.plist"
    sed -e "s#__USER__#$(whoami)#g" -e "s#__PYTHON__#$PY#g" -e "s#__RUNTIME__#$RUNTIME#g" \
        -e "s#__VHOME__#$VHOME#g" -e "s#__AGE__#$AGE#g" -e "s#__SCAN_ROOTS__#$AX_SCAN_ROOTS#g" \
        -e "s#__SLACK_DM__#${AX_SLACK_DM:-}#g" -e "s#__SLACK_BOT_ENV__#${AX_SLACK_BOT_ENV:-}#g" \
        "$PKG/launchd/com.__USER__.ax-autoscan.plist.tmpl" > "$PL"
    launchctl unload "$PL" 2>/dev/null || true; launchctl load "$PL" 2>/dev/null && say "已排程每日自動歸檔(launchd)" || true
  else
    LINE="15 9 * * * . $CFG/env; $PY $RUNTIME/ax_vault_autoscan.py >> $VHOME/autoscan.log 2>&1"
    ( crontab -l 2>/dev/null | grep -v ax_vault_autoscan; echo "$LINE" ) | crontab - 2>/dev/null && say "已排程每日自動歸檔(cron)" || say "(排程略過：此環境無 cron)"
  fi
fi

# 技能 plugin
if [ "$NO_PLUGIN" = 0 ] && command -v claude >/dev/null 2>&1; then
  claude plugin marketplace add "$REPO" >/dev/null 2>&1 || true
  claude plugin install ax@ax-workflow >/dev/null 2>&1 || true
  say "已安裝 AX 技能"
fi

# 首裝才 baseline（更新不重跑）
[ "$IS_UPDATE" = 0 ] && { "$PY" "$RUNTIME/ax_vault_autoscan.py" --seed >/dev/null 2>&1 || true; say "既有機密已歸檔入庫"; }

echo ""
echo "✅ 完成！"
[ "$PUB" != "?" ] && { echo "把下面這一行貼給管理員（你的金鑰，不是密碼、可公開）："; echo "    $PUB"; }
echo "之後照常工作即可；每日會自動把新機密歸檔。"
