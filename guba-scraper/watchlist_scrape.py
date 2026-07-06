"""Scrape the 5 watchlist stocks first."""
import re, time, requests, sqlite3

DB_FILE = "st_guba.db"
WATCH = [("300301","ST长方"),("002211","ST宏达"),("002816","*ST和科"),("300020","ST银江"),("002102","ST能特")]

db = sqlite3.connect(DB_FILE)
db.execute("CREATE TABLE IF NOT EXISTS posts(post_id INTEGER PRIMARY KEY,stock_code TEXT,stock_name TEXT,title TEXT,author TEXT,publish_time TEXT,reads INTEGER,comments INTEGER)")
db.commit()

for code, name in WATCH:
    before = db.execute("SELECT COUNT(*) FROM posts WHERE stock_code=?",(code,)).fetchone()[0]
    total_new = 0

    for pg in range(1, 200):
        try:
            r = requests.get(f"https://guba.eastmoney.com/list,{code}_{pg}.html",
                           headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        except:
            continue

        ids = re.findall(r'"post_id"\s*:\s*(\d+)', r.text)
        if not ids and pg > 3:
            break

        titles = re.findall(r'"post_title"\s*:\s*"([^"]*)"', r.text)
        times = re.findall(r'"post_display_time"\s*:\s*"([^"]+)"', r.text)
        reads = re.findall(r'"post_click_count"\s*:\s*(\d+)', r.text)
        comments = re.findall(r'"post_comment_count"\s*:\s*(\d+)', r.text)
        users = re.findall(r'"user_nickname"\s*:\s*"([^"]*)"', r.text)
        bar_m = re.search(r'"stockbar_name"\s*:\s*"([^"]*)"', r.text)
        bar_name = bar_m.group(1) if bar_m else ""

        new_count = 0
        for i in range(min(len(ids),len(titles),len(times))):
            try:
                db.execute("INSERT INTO posts VALUES(?,?,?,?,?,?,?,?)",
                    (int(ids[i]),code,bar_name,titles[i],users[i] if i<len(users) else "",times[i],int(reads[i]) if i<len(reads) else 0,int(comments[i]) if i<len(comments) else 0))
                new_count += 1
            except sqlite3.IntegrityError:
                pass

        if new_count == 0 and len(ids) > 0 and pg > 5:
            break

        total_new += new_count
        if pg % 20 == 0:
            db.commit()
            print(f"  {code} {name}: pg{pg} +{new_count}", flush=True)
        time.sleep(0.8)

    db.commit()
    after = db.execute("SELECT COUNT(*) FROM posts WHERE stock_code=?",(code,)).fetchone()[0]
    print(f"  ✅ {code} {name}: +{total_new} ({before}→{after})", flush=True)
    time.sleep(3)

total = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
print(f"\nTotal: {total:,} posts", flush=True)
db.close()
