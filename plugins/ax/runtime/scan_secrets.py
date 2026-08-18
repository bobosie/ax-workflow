#!/usr/bin/env python3
"""掃描本機散落的機密（帳密/TOTP/API key/token/私鑰/連線字串），輸出：
  - /tmp/axv-scan/inventory.jsonl  (600, 含原值，供 import)
  - /tmp/axv-scan/report_masked.txt (遮值，供人/agent 檢視)
偵測＝正則高訊號 + 佔位符過濾 + 跨拷貝以 value-hash 去重。不改任何來源檔（唯讀）。"""
import os, re, json, hashlib, sys

ROOTS = [os.path.expanduser(p) for p in (os.environ.get("AX_SCAN_ROOTS") or
         "~/Projects:~/Tool:~/.claude:~/.config").split(":")]
EXCL_DIR = {"node_modules",".git",".venv","venv","ms-playwright","__pycache__",".pub-cache",
            "fvm",".nvm","dist","build",".cache","Caches",".ax-vault"}
EXCL_PATH = ("/Library/Caches/","/.Trash/")
SKIP_FILES = {os.path.expanduser("~/.config/totp/secrets.json")}   # TOTP 已於 P1 匯入
EXTS = (".md",".env",".json",".sh",".py",".js",".ts",".txt",".yaml",".yml",".conf",".ini",".toml",".cfg")
MAXSZ = 2_000_000

KEY = r"(login_password|withdraw_password|passwd|password|pwd|密碼|登入密碼|取款密碼|totp_secret|otp_secret|secret_key|access_key|api[_-]?key|client_secret|auth_token|api_token|access_token|bearer|private_key|secret)"
KV = re.compile(KEY + r"""['"` ]{0,3}[:=]['"` ]{0,3}([A-Za-z0-9+/_=@.!#$%^&*\-]{6,})""", re.I)
STANDALONE = [
    ("age_key", re.compile(r"AGE-SECRET-KEY-1[0-9A-Z]{20,}")),
    ("pem_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("slack_token", re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")),
    ("github_token", re.compile(r"gh[pousr]_[0-9A-Za-z]{20,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{6,}")),
    ("hex32", re.compile(r"\b[0-9a-f]{32}\b")),
    ("url_cred", re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^:@/\s]+:([^:@/\s]{4,})@")),
]
PLACE = re.compile(r"(x{3,}|<[^>]{2,}>|redacted|例如|範例|your[_-]|changeme|placeholder|\*{3,}|\.\.\.|\$\{|\$\(|"
                   r"process\.env|os\.environ|getenv|%s|\{\{|dummy|example\.com|test_?123|foo|bar|"
                   r"abcdef|123456789|<value>|\.\.\.\.)", re.I)
# hex32 常誤中 git sha / md5；只在鍵含 token/key/secret 的上下文或已知欄位才採信
HEXCTX = re.compile(r"(token|key|secret|密|pass|api|auth|jenkins)", re.I)

def masked(v):
    v=str(v)
    return (v[:2]+"…"+str(len(v))+"chars") if len(v)>4 else "****"

def entity_from_path(fp, line):
    base=os.path.basename(fp)
    # 從檔名/路徑猜服務或帳號用途
    m=re.search(r"(jenkins|slack|atlassian|jira|confluence|gitlab|github|oracle|mysql|redis|kafka|"
                r"cloudflare|aws|oss|vault|totp|db)", fp, re.I)
    return (m.group(1).lower() if m else base)

def main():
    out=os.path.expanduser("/tmp/axv-scan"); os.makedirs(out,exist_ok=True); os.chmod(out,0o700)
    inv=open(os.path.join(out,"inventory.jsonl"),"w"); rpt=open(os.path.join(out,"report_masked.txt"),"w")
    seen_val={}; n_hits=0; n_files=0; kinds={}
    for root in ROOTS:
        for dp,dns,fns in os.walk(root):
            dns[:]=[d for d in dns if d not in EXCL_DIR]
            if any(x in dp for x in EXCL_PATH): continue
            for fn in fns:
                fp=os.path.join(dp,fn)
                if fp in SKIP_FILES: continue
                low=fn.lower()
                if not (low.endswith(EXTS) or ".env" in low or ".bak" in low): continue
                try:
                    if os.path.getsize(fp)>MAXSZ: continue
                    txt=open(fp,encoding="utf-8",errors="ignore").read()
                except Exception: continue
                found_in_file=False
                for i,line in enumerate(txt.splitlines(),1):
                    if len(line)>600: continue
                    cands=[]
                    for m in KV.finditer(line):
                        key,val=m.group(1),m.group(2)
                        cands.append(("password" if re.search(r"pass|密碼|pwd",key,re.I) else
                                      "totp" if "totp" in key.lower() or "otp" in key.lower() else
                                      "token_or_key", key, val))
                    for kind,rx in STANDALONE:
                        for m in rx.finditer(line):
                            val=m.group(1) if m.groups() else m.group(0)
                            if kind=="hex32" and not HEXCTX.search(line): continue
                            cands.append((kind, kind, val))
                    for kind,key,val in cands:
                        if PLACE.search(val) or PLACE.search(line): continue
                        if len(set(val))<=2: continue
                        vh=hashlib.sha256(val.encode()).hexdigest()[:16]
                        rec={"file":fp,"line":i,"kind":kind,"key":key,"value":val,"vhash":vh,
                             "entity":entity_from_path(fp,line),"masked":masked(val)}
                        inv.write(json.dumps(rec,ensure_ascii=False)+"\n")
                        rpt.write(f"{kind:14} {rec['entity']:16} {masked(val):16} {fp}:{i}\n")
                        seen_val.setdefault(vh,[]).append(fp); kinds[kind]=kinds.get(kind,0)+1
                        n_hits+=1; found_in_file=True
                if found_in_file: n_files+=1
    inv.close(); rpt.close()
    os.chmod(os.path.join(out,"inventory.jsonl"),0o600)
    print(f"命中 {n_hits} 行 / {n_files} 檔 / 去重後唯一祕密值 {len(seen_val)} 個")
    print("依類型：",json.dumps(kinds,ensure_ascii=False))
    multi=sum(1 for v in seen_val.values() if len(v)>1)
    print(f"跨拷貝散落（同值出現在≥2檔）的祕密：{multi} 個")

if __name__=="__main__": main()
