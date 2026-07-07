"""批量抓取 V2 — 修复提前退出 + 分页检测。"""
import re, time, requests, sqlite3, json, os

DELAY = 1.5
STOCK_DELAY = 5
DB_FILE = "st_guba.db"
PROGRESS_FILE = "progress.json"

def get_st_list():
    try:
        import baostock as bs
        bs.login()
        rs = bs.query_stock_basic(code_name="ST")
        data = rs.get_data()
        bs.logout()
        active = data[data["status"] == "1"]
        codes = []
        for _, row in active.iterrows():
            c = row["code"].replace("sh.", "").replace("sz.", "")
            codes.append((c, row["code_name"]))
        if codes: return codes
    except: pass
    return [("002141", "贤丰控股"), ("600079", "ST人福"), ("600053", "*ST九鼎")]

def get_total_pages(code):
    try:
        r = requests.get(f"https://guba.eastmoney.com/list,{code}.html",
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        m = re.search(r'"count"\s*:\s*(\d+)', r.text)
        if m:
            return int(m.group(1)) // 80 + 1
    except: pass
    return 100

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
    for i in range(min(len(ids), len(titles), len(times))):
        posts.append((int(ids[i]), code, bar_name, titles[i],
                      users[i] if i < len(users) else "",
                      times[i],
                      int(reads[i]) if i < len(reads) else 0,
                      int(comments[i]) if i < len(comments) else 0))
    return posts

def main():
    stocks = get_st_list()
    print(f"共 {len(stocks)} 只 ST 股票")

    progress = {}
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            progress = json.load(f)
    completed = progress.get("completed", {})
    resume_stock = progress.get("current_stock")
    resume_page = progress.get("current_page", 1)

    db = sqlite3.connect(DB_FILE)
    db.execute("CREATE TABLE IF NOT EXISTS posts(post_id INTEGER PRIMARY KEY,stock_code TEXT,stock_name TEXT,title TEXT,author TEXT,publish_time TEXT,reads INTEGER,comments INTEGER)")
    db.commit()

    total_new = 0
    started = not resume_stock

    for i, (code, name) in enumerate(stocks):
        if not started:
            if code == resume_stock:
                started = True
            else:
                continue
        if code in completed and code != resume_stock:
            continue

        total_pages = get_total_pages(code)
        sp = resume_page if code == resume_stock else 1
        resume_stock = None

        stock_posts = 0
        empty_streak = 0

        for pg in range(sp, min(total_pages + 1, 5000)):
            posts = scrape_page(code, pg)

            if len(posts) == 0:
                empty_streak += 1
                if empty_streak >= 10 and pg > 50:
                    break
            else:
                empty_streak = 0
                db.executemany(
                    "INSERT OR IGNORE INTO posts VALUES(?,?,?,?,?,?,?,?)", posts)
                db.commit()
                stock_posts += len(posts)
                total_new += len(posts)

            if pg % 50 == 0:
                t = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
                print(f"  [{i+1}] {code} {name}: pg{pg}/{total_pages} stock:{stock_posts} total:{t:,}")
                with open(PROGRESS_FILE, "w") as f:
                    json.dump({"completed": completed, "current_stock": code, "current_page": pg}, f)

            time.sleep(DELAY)

        completed[code] = total_pages
        with open(PROGRESS_FILE, "w") as f:
            json.dump({"completed": completed, "current_stock": None, "current_page": 1}, f)

        t = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        print(f"  ✅ [{i+1}] {code} {name}: done {total_pages}pg → {stock_posts}帖 | DB:{t:,}")
        time.sleep(STOCK_DELAY)

    t = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    print(f"\n完成! {t:,} 条帖子")
    db.close()

if __name__ == "__main__":
    main()
