import re, time, requests, sqlite3, random
from concurrent.futures import ThreadPoolExecutor, as_completed

DB = "st_guba.db"
WATCH = {"002211":"ST宏达","300301":"ST长方","688646":"ST逸飞","002168":"ST惠程","600079":"ST人福"}

def sp(code, pg):
    try: r = requests.get(f"https://guba.eastmoney.com/list,{code}_{pg}.html",headers={"User-Agent":"Mozilla/5.0"},timeout=15)
    except: return []
    ids=re.findall(r'"post_id"\s*:\s*(\d+)',r.text)
    titles=re.findall(r'"post_title"\s*:\s*"([^"]*)"',r.text)
    times=re.findall(r'"post_display_time"\s*:\s*"([^"]+)"',r.text)
    reads=re.findall(r'"post_click_count"\s*:\s*(\d+)',r.text)
    comments=re.findall(r'"post_comment_count"\s*:\s*(\d+)',r.text)
    users=re.findall(r'"user_nickname"\s*:\s*"([^"]*)"',r.text)
    bn=re.search(r'"stockbar_name"\s*:\s*"([^"]*)"',r.text)
    posts=[]
    for i in range(min(len(ids),len(titles),len(times))):
        posts.append((int(ids[i]),code,bn.group(1) if bn else "",titles[i],users[i] if i<len(users) else "",times[i],int(reads[i]) if i<len(reads) else 0,int(comments[i]) if i<len(comments) else 0))
    return posts

def run(code, name):
    ex = 0
    try:
        db0 = sqlite3.connect(DB); ex = db0.execute("SELECT COUNT(*) FROM posts WHERE stock_code=?",(code,)).fetchone()[0]; db0.close()
    except: pass
    pg = ex // 80 + 1; es = ds = nc = 0
    print(f"  [{name}] pg{pg} (have {ex:,})", flush=True)
    while True:
        posts = sp(code, pg)
        if not posts:
            es += 1; ds = 0; time.sleep(random.uniform(5,8))
            if es > 30: break; continue
        es = 0; ins = 0
        db = sqlite3.connect(DB, timeout=30)
        for p in posts:
            try: db.execute("INSERT OR IGNORE INTO posts VALUES(?,?,?,?,?,?,?,?)",p); ins += 1
            except: pass
        db.commit(); db.close()
        nc += ins
        if ins == 0: ds += 1
        else: ds = 0
        pg += 1
        if pg % 50 == 0:
            db2 = sqlite3.connect(DB); t = db2.execute("SELECT COUNT(*) FROM posts").fetchone()[0]; db2.close()
            print(f"  [{name}] pg{pg} | DB:{t:,}", flush=True)
        if ds > 100: break
        time.sleep(random.uniform(5, 8))
    return code, name, nc

print("2 threads | INSERT OR IGNORE | fresh connection per page\n")
with ThreadPoolExecutor(max_workers=2) as pool:
    futures = {pool.submit(run, c, n): c for c, n in WATCH.items()}
    for f in as_completed(futures):
        code, name, count = f.result()
        db2 = sqlite3.connect(DB); t = db2.execute("SELECT COUNT(*) FROM posts").fetchone()[0]; db2.close()
        print(f"  ✅ {code} {name}: +{count:,} | DB:{t:,}", flush=True)
db2 = sqlite3.connect(DB); t = db2.execute("SELECT COUNT(*) FROM posts").fetchone()[0]; db2.close()
print(f"\nDone! {t:,}", flush=True)
