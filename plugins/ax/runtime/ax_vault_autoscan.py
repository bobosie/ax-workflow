#!/usr/bin/env python3
"""AX Vault 自動歸檔哨兵（每日 launchd）。
偵測「新出現、尚未入庫」的機密 → 高信任自動入 vault、其餘列待審 → Slack DM 遮值摘要。
值不進 DM/log；掃描明碼 inventory 用後即 shred。"""
import os,re,json,subprocess,hashlib,glob,sys,time,urllib.request

HOME=os.path.expanduser("~"); HERE=os.path.dirname(os.path.abspath(__file__))
VAULT=os.environ.get("AX_VAULT_BIN",HERE+"/vault")          # 同目錄；封裝到別處也能用
SCAN=os.environ.get("AX_SCAN_BIN",HERE+"/scan_secrets.py")
AGE=os.environ.get("AX_VAULT_AGE","/opt/homebrew/bin/age"); ID=os.environ.get("AX_VAULT_HOME",HOME+"/.ax-vault")+"/identity/age.key"
INV="/tmp/axv-scan/inventory.jsonl"
SEEN=HOME+"/.ax-vault/.autoscan-seen.json"; PENDING=HOME+"/.ax-vault/pending_review.md"
BOT_ENV=os.environ.get("AX_SLACK_BOT_ENV",HOME+"/.config/claude-rc/bot.env"); DM_CHANNEL=os.environ.get("AX_SLACK_DM","")   # 未設＝不發 DM
DRY="--dry-run" in sys.argv
SEED="--seed" in sys.argv   # 首輪：入庫 high、靜默 baseline low（既有語料已由 rounds1-3 徹查）、不 DM

NOISE=re.compile(r'/plugins/marketplaces/|/tests?/|/test_|_test\.|/scrub-stress/|/harvest-e2e/|/node_modules/|'
                 r'/chrome-cdp/|\.example|secret_scanner|redaction_|'
                 r'gen_testset|_poc_|/eval/|/\.dd-compare/|/\.worktrees/|/locale/|package-lock',re.I)
STRUCT=re.compile(r'\.(json|ya?ml|conf|ini|toml|env)$|\.env\.',re.I)
PLACE=re.compile(r'(x{3,}|<[^>]+>|redacted|your[_-]|changeme|placeholder|\$\{|\$\(|example|dummy|process\.env|os\.getenv|os\.environ)',re.I)
KNOWN=('age_key','pem_key','aws_key','slack_token','github_token')
COMMON=set("password passwd admin secret token example test true false none null localhost default changeme root user pass".split())

def credlike(v):
    if v.lower() in COMMON or len(v)<6: return False
    if re.fullmatch(r'\d{6,}',v): return True
    cats=sum([bool(re.search(r'[a-z]',v)),bool(re.search(r'[A-Z]',v)),bool(re.search(r'\d',v)),bool(re.search(r'[^A-Za-z0-9]',v))])
    return cats>=3 or len(v)>=16 or bool(re.search(r'(AKIA|xox|gh[pousr]_|AGE-SECRET|-----BEGIN|sk-)',v))

def vault_vhashes():
    s=set()
    for ap in glob.glob(HOME+"/.ax-vault/secrets/*/*.age"):
        try:d=json.loads(subprocess.run([AGE,"-d","-i",ID,ap],capture_output=True).stdout)
        except:continue
        for v in (d.get("secrets") or {}).values(): s.add(hashlib.sha256(str(v).encode()).hexdigest()[:16])
    return s

def name_for(fp,tenant):
    rel=fp.replace(HOME+"/",""); parts=[p for p in rel.split("/") if p not in ("Projects","conf","config","env",".memsearch","memory")]
    stem=re.sub(r"\.(json|ya?ml|conf|env|sh|ts|py|js|md|bak.*)$","",parts[-1])
    return re.sub(r"[^a-z0-9-]+","-",f"auto-{parts[0].replace('.','')}-{stem}".lower()).strip("-")[:48]
def tenant_for(fp):
    if "/dt-k8s-rel-deploy/" in fp: return "infra"
    if "/.config/" in fp: return "token"
    if "-e2e/" in fp or "/e2e/" in fp: return "e2e"
    return "infra" if STRUCT.search(fp) else "personal"

def slack_dm(text):
    if not DM_CHANNEL.strip(): return   # 未設 AX_SLACK_DM（如他人安裝）→ 不誤送
    try:
        tok=""
        for ln in open(BOT_ENV):
            if "CLAUDE_RC_BOT_TOKEN" in ln: tok=ln.split("=",1)[1].strip().strip('"')
        if not tok: return
        data=json.dumps({"channel":DM_CHANNEL,"text":text,"unfurl_links":False}).encode()
        req=urllib.request.Request("https://slack.com/api/chat.postMessage",data=data,
            headers={"Authorization":f"Bearer {tok}","Content-Type":"application/json"})
        urllib.request.urlopen(req,timeout=15).read()
    except Exception as e:
        print("[autoscan] slack DM 失敗:",e,file=sys.stderr)

def _rm_inventory():
    if os.path.exists(INV):
        try: subprocess.run(["shred","-u",INV],capture_output=True,check=True)
        except Exception:
            try: os.remove(INV)
            except OSError: pass
    # 連同 masked report / 候選檔清單（含定位資訊）一併清掉整個工作目錄
    import shutil
    shutil.rmtree("/tmp/axv-scan",ignore_errors=True)

def main():
    subprocess.run([sys.executable,SCAN],capture_output=True)
    if not os.path.exists(INV): print("[autoscan] 無 inventory"); return
    seen=json.load(open(SEEN)) if os.path.exists(SEEN) else {}
    vv=vault_vhashes()
    recs=[json.loads(l) for l in open(INV,encoding="utf-8")]
    new_high={}; new_low=[]; nseen=0
    for r in recs:
        fp,v,k,vh=r["file"],r["value"],r["kind"],r["vhash"]
        if NOISE.search(fp) or k in ("hex32","jwt"): continue
        if PLACE.search(v) or v.startswith("$") or not credlike(v): continue
        if vh in vv or vh in seen: continue
        high = (k in KNOWN) or ("/.config/" in fp) or bool(STRUCT.search(fp))
        if high: new_high.setdefault(fp,[]).append(r)
        elif not SEED: new_low.append(r)
        seen[vh]={"first":int(os.path.getmtime(fp)),"kind":k,"file":fp,"status":"vaulted" if high else "pending"}
        nseen+=1
    # 自動入庫 high
    vaulted=[]
    for fp,rs in new_high.items():
        t=tenant_for(fp); nm=name_for(fp,t); fields={}
        for r in rs:
            key=re.sub(r"[^a-z0-9_]","_",(r["key"] or r["kind"]).lower())[:28] or "secret"
            kk=key;n=2
            while kk in fields and fields[kk]!=r["value"]: kk=f"{key}_{n}";n+=1
            fields[kk]=r["value"]
        if DRY: vaulted.append((nm,len(fields),fp)); continue
        p=subprocess.run([sys.executable,VAULT,"add",nm,"--tenant",t,"--note",f"auto-archived {fp.replace(HOME,'~')}","--secret-stdin"],
                         input=("\n".join(f"{k}={v}" for k,v in fields.items())+"\n").encode(),capture_output=True)
        if p.returncode==0: vaulted.append((nm,len(fields),fp))
    # 待審清單（遮值）
    if new_low:
        with open(PENDING,"a") as f:
            for r in new_low: f.write(f"- [{r['kind']}] {r['file'].replace(HOME,'~')}:{r['line']}  (vault add 後把 vhash 記入 seen)\n")
    if not DRY: json.dump(seen,open(SEEN,"w"))
    _rm_inventory()  # 清明碼 inventory（macOS 無 shred 則 os.remove）
    # DM（只在有新項時）
    if nseen and not DRY and not SEED:
        lines=[f"🔐 *AX Vault 自動歸檔* ({time.strftime('%Y-%m-%d')})",
               f"偵測 {nseen} 個新機密；自動入庫 {len(vaulted)}，待審 {len(new_low)}"]
        for nm,c,fp in vaulted[:15]: lines.append(f"  ✅ `{nm}` ({c}欄)")
        if len(vaulted)>15: lines.append(f"  …+{len(vaulted)-15} 更多")
        if new_low: lines.append(f"  ⚠️ {len(new_low)} 待審（prose/code）見 ~/.ax-vault/pending_review.md")
        lines.append("_值不入訊息；如有誤收 `vault` 手動移除即可_")
        slack_dm("\n".join(lines))
    print(f"[autoscan] new={nseen} vaulted_entries={len(vaulted)} low_pending={len(new_low)}"+(" (DRY)" if DRY else ""))

if __name__=="__main__": main()
