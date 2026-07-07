"""V3 scraper — skip existing posts, prioritize watchlist stocks."""
import re, time, requests, sqlite3, json, os

DELAY = 1.0
STOCK_DELAY = 3
DB_FILE = "st_guba.db"
WATCH = {"300301", "002211", "002816", "300020", "002102"}

def get_st_list():
    try:
        import baostock as bs
        bs.login()
        rs = bs.query_stock_basic(code_name="ST")
        data = rs.get_data()
        bs.logout()
        active = data[data["status"] == "1"]
        codes = [(r["code"].replace("sh.","").replace("sz.",""), r["code_name"]) for _,r in active.iterrows()]
        return codes
    except: return []

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
        posts.append((int(ids[i]),code,bar_name,titles[i],users[i] if i<len(users) else "",times[i],int(reads[i]) if i<len(reads) else 0,int(comments[i]) if i<len(comments) else 0))
    return posts

db = sqlite3.connect(DB_FILE)
db.execute("CREATE TABLE IF NOT EXISTS posts(post_id INTEGER PRIMARY KEY,stock_code TEXT,stock_name TEXT,title TEXT,author TEXT,publish_time TEXT,reads INTEGER,comments INTEGER)")
db.commit()

stocks = get_st_list()
if not stocks:
    print("No stocks!"); exit(1)

watch = [s for s in stocks if s[0] in WATCH]
rest = [s for s in stocks if s[0] not in WATCH]
stocks = watch + rest
print(f"共 {len(stocks)} 只 (优先 {len(watch)} 只关注股: {[s[1] for s in watch]})")

for code, name in stocks:
    total_new = 0
    for pg in range(1, 5000):
        posts = scrape_page(code, pg)
        if not posts:
            if pg > 10: break
            time.sleep(DELAY); continue

        new_posts = [p for p in posts if not db.execute("SELECT 1 FROM posts WHERE post_id=?", (p[0],)).fetchone()]
        if len(new_posts) == 0 and pg > 5:
            break  # reached existing data

        if new_posts:
            db.executemany("INSERT OR IGNORE INTO posts VALUES(?,?,?,?,?,?,?,?)", new_posts)
            db.commit()
            total_new += len(new_posts)

        if pg % 100 == 0:
            t = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            print(f"  {code} {name}: pg{pg} +{total_new} total:{t:,}")

        time.sleep(DELAY)

    t = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    sc = db.execute("SELECT COUNT(DISTINCT stock_code) FROM posts").fetchone()[0]
    print(f"  {'✅' if total_new > 0 else '⏭️'} {code} {name}: +{total_new} | DB:{t:,}帖 {sc}股")
    time.sleep(STOCK_DELAY)

print(f"\nDone! {db.execute('SELECT COUNT(*) FROM posts').fetchone()[0]:,} posts")
db.close()
