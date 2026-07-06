"""多线程 ST 股吧批量抓取 — 10 threads, 3-5s jitter, never get banned."""
import re, time, requests, sqlite3, random
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

DB_FILE = "st_guba.db"
MAX_THREADS = 10
PAGE_DELAY = (2.0, 4.0)  # random 2-4s between pages per thread
db_lock = Lock()

def get_st_list():
    try:
        import baostock as bs
        bs.login()
        rs = bs.query_stock_basic(code_name="ST")
        data = rs.get_data()
        bs.logout()
        return [(r["code"].replace("sh.","").replace("sz.",""), r["code_name"])
                for _, r in data[data["status"]=="1"].iterrows()]
    except:
        return [("300301","ST长方"),("002211","ST宏达"),("002816","*ST和科"),
                ("300020","ST银江"),("002102","ST能特"),("600053","*ST九鼎"),
                ("600079","ST人福"),("002141","贤丰控股")]

def scrape_page(code, page):
    url = f"https://guba.eastmoney.com/list,{code}_{page}.html"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    except:
        return []
    ids = re.findall(r'"post_id"\s*:\s*(\d+)', r.text)
    titles = re.findall(r'"post_title"\s*:\s*"([^"]*)"', r.text)
    times = re.findall(r'"post_display_time"\s*:\s*"([^"]+)"', r.text)
    reads = re.findall(r'"post_click_count"\s*:\s*(\d+)', r.text)
    comments = re.findall(r'"post_comment_count"\s*:\s*(\d+)', r.text)
    users = re.findall(r'"user_nickname"\s*:\s*"([^"]*)"', r.text)
    bar_m = re.search(r'"stockbar_name"\s*:\s*"([^"]*)"', r.text)
    bar_name = bar_m.group(1) if bar_m else ""
    posts = []
    for i in range(min(len(ids),len(titles),len(times))):
        posts.append((int(ids[i]),code,bar_name,titles[i],
                      users[i] if i<len(users) else "",times[i],
                      int(reads[i]) if i<len(reads) else 0,
                      int(comments[i]) if i<len(comments) else 0))
    return posts

def scrape_stock(code, name):
    """Scrape one stock fully. Called per thread."""
    new_count = 0
    db = sqlite3.connect(DB_FILE)
    db.execute("CREATE TABLE IF NOT EXISTS posts(post_id INTEGER PRIMARY KEY,stock_code TEXT,stock_name TEXT,title TEXT,author TEXT,publish_time TEXT,reads INTEGER,comments INTEGER)")
    db.commit()

    for pg in range(1, 5000):
        posts = scrape_page(code, pg)
        if not posts:
            if pg > 10: break
            time.sleep(random.uniform(*PAGE_DELAY))
            continue

        inserted = 0
        for p in posts:
            try:
                db.execute("INSERT INTO posts VALUES(?,?,?,?,?,?,?,?)", p)
                inserted += 1
            except sqlite3.IntegrityError:
                pass

        if inserted == 0 and pg > 5:
            break  # all duplicates = reached existing data

        with db_lock:
            db.commit()

        new_count += inserted
        if pg % 50 == 0:
            t = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            print(f"  [{name}] pg{pg} +{inserted} | total:{t:,}", flush=True)

        time.sleep(random.uniform(*PAGE_DELAY))

    db.commit()
    db.close()
    return code, name, new_count

# ── Main ──
stocks = get_st_list()
print(f"共 {len(stocks)} 只 ST | {MAX_THREADS} threads | {PAGE_DELAY[0]}-{PAGE_DELAY[1]}s/page\n")

# Only scrape stocks not yet in DB
db_init = sqlite3.connect(DB_FILE)
existing = set(r[0] for r in db_init.execute("SELECT DISTINCT stock_code FROM posts").fetchall())
db_init.close()

todo = [(c,n) for c,n in stocks if c not in existing]
print(f"已入库: {len(existing)} 只 | 待抓取: {len(todo)} 只\n")

with ThreadPoolExecutor(max_workers=MAX_THREADS) as pool:
    futures = {pool.submit(scrape_stock, c, n): (c, n) for c, n in todo}
    for f in as_completed(futures):
        code, name, count = f.result()
        t = sqlite3.connect(DB_FILE).execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        print(f"  ✅ {code} {name}: +{count}帖 | DB:{t:,}", flush=True)

final = sqlite3.connect(DB_FILE).execute("SELECT COUNT(*) FROM posts").fetchone()[0]
print(f"\nDone! {final:,} posts")
