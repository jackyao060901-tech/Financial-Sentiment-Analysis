"""Final: dup break + lock retry + 3 threads"""
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
    db = sqlite3.connect(DB, timeout=60)
    db.execute("PRAGMA journal_mode=WAL")
    ex = db.execute("SELECT COUNT(*) FROM posts WHERE stock_code=?",(code,)).fetchone()[0]
    pg = ex // 80 + 1; es = ds = nc = 0
    print(f"  [{name}] pg{pg} (have {ex:,})", flush=True)
    while True:
        posts = sp(code, pg)
        if not posts:
            es += 1; ds = 0
            time.sleep(random.uniform(5,8))
            if es > 20: break; continue
        else:
            es = 0
            ins = 0
            for p in posts:
                for retry in range(5):
                    try: db.execute("INSERT INTO posts VALUES(?,?,?,?,?,?,?,?)",p); ins += 1; break
                    except sqlite3.IntegrityError: break
                    except sqlite3.OperationalError: time.sleep(0.5)
            if ins > 0:
                try: db.commit()
                except: time.sleep(0.5); db.commit()
                nc += ins; ds = 0
            else:
                ds += 1  # duplicate page
        pg += 1
        if pg % 50 == 0:
            t = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            print(f"  [{name}] pg{pg} | DB:{t:,}", flush=True)
        if ds > 100:  # 100 consecutive duplicate pages = end
            break
        time.sleep(random.uniform(5, 8))
    db.commit(); db.close()
    return code, name, nc

print("3 threads | 5-8s | dup break at 100 pages\n")
with ThreadPoolExecutor(max_workers=3) as pool:
    futures = {pool.submit(run, c, n): c for c, n in WATCH.items()}
    for f in as_completed(futures):
        code, name, count = f.result()
        t = sqlite3.connect(DB).execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        print(f"  ✅ {code} {name}: +{count:,} | DB:{t:,}", flush=True)
print(f"\nDone! {sqlite3.connect(DB).execute('SELECT COUNT(*) FROM posts').fetchone()[0]:,}", flush=True)
