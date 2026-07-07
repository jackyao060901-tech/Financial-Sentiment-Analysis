"""ST 股股吧采集器(整合版)——吸收老师 guba-scraper 的可取之处 + 本仓库统一结构。

融合了老师方法里被验证有效的几点(见 guba-scraper/ANTI_BAN_GUIDE.md):
  1. **SQLite + post_id 主键去重**:天然幂等,反复跑不重复,适合大批量/断点续采。
  2. **多线程跨多只股票并行**:分散访问(像浏览多个吧),而非死磕一只翻几百页 → 不易被封。
  3. **拟人延时**:页间随机 2.5~4.5s、换股 5~8s(老师实测住宅 IP 下 1100 页未被封)。
  4. **按已有行数断点续采**:`pg = 已有行数 // 80 + 1`,中断后自动从上次位置继续。
  5. **停止条件**:连续空页(疑到底/限流)或回溯到目标起始日期。
本仓库的贡献:复用 crawlers/eastmoney_guba 的稳健 JSON 提取 + 统一字段;可一键导出 CSV。

用法:
  python scripts/collect_st_guba.py                 # 采 5 只 ST 到 2020,多线程
  python scripts/collect_st_guba.py --since 2020-01-01 --threads 3 --pmin 2.5 --pmax 4.5
  python scripts/collect_st_guba.py --export        # 把 DB 导出为 data/st_since2020/*.csv
"""
import os
import sys
import csv
import glob
import time
import random
import sqlite3
import argparse
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "crawlers"))
import eastmoney_guba as g          # noqa: E402  复用稳健的内嵌 JSON 提取
from common import make_session     # noqa: E402

DB_PATH = "data/st_guba.db"
DATA_DIR = "data/st_since2020"
STOCKS = [
    ("300301", "ST长方"), ("002816", "ST和科"), ("688646", "ST逸飞"),
    ("688076", "ST诺泰"), ("002055", "ST得润"),
]
BASE = "https://guba.eastmoney.com"
_db_lock = Lock()


def init_db(path):
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS posts(
            post_id INTEGER PRIMARY KEY, stock_code TEXT, stock_name TEXT,
            title TEXT, author TEXT, author_id TEXT, publish_time TEXT,
            reads INTEGER, comments INTEGER, forwards INTEGER,
            bullish_bearish TEXT, url TEXT, crawl_time TEXT);
        CREATE INDEX IF NOT EXISTS idx_stock ON posts(stock_code);
        CREATE INDEX IF NOT EXISTS idx_time ON posts(publish_time);
    """)
    db.commit()
    return db


def _row(x):
    """把 eastmoney_guba 的统一字段 dict 转成 DB 行。"""
    def i(v):
        try: return int(v)
        except (ValueError, TypeError): return 0
    return (i(x["post_id"]), x["stock_code"], "", x["title"], x["author"],
            str(x["author_id"]), x["publish_time"], i(x["read_count"]),
            i(x["comment_count"]), i(x["forward_count"]),
            str(x["bullish_bearish"]), x["url"], x["crawl_time"])


def scrape_stock(code, name, since, pmin, pmax, empty_limit):
    """单只股票:断点续采 → 逐页抓 → INSERT OR IGNORE → 到 since 或撞墙停。"""
    session = make_session()
    with _db_lock:
        db = sqlite3.connect(DB_PATH, timeout=60)
        have = db.execute("SELECT COUNT(*) FROM posts WHERE stock_code=?", (code,)).fetchone()[0]
        db.close()
    page = have // 80 + 1
    empties = new = 0
    print(f"  [{name}] 从第 {page} 页续(已有 {have} 条)", flush=True)
    while True:
        seg = "" if page == 1 else f"_{page}"
        try:
            r = session.get(f"{BASE}/list,{code}{seg}.html",
                            headers={"Referer": BASE + "/"}, timeout=20)
            rows = g.parse_page(r.text, code) if r.status_code == 200 else []
        except Exception:
            rows = []
        if not rows:
            empties += 1
            if empties >= empty_limit:
                return code, name, new, f"连续{empties}页空(到底/限流),停第{page}页"
            time.sleep(random.uniform(pmin * 2, pmax * 2))
            continue
        empties = 0
        with _db_lock:
            db = sqlite3.connect(DB_PATH, timeout=60)
            for x in rows:
                db.execute("INSERT OR IGNORE INTO posts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", _row(x))
            db.commit(); db.close()
        new += len(rows)
        oldest = min((x["publish_time"] for x in rows if x["publish_time"]), default="")
        if page % 20 == 0:
            print(f"  [{name}] 第{page}页 最旧{oldest[:10]}", flush=True)
        if oldest and oldest < since:
            return code, name, new, f"已回溯到 {since}(第{page}页),完成"
        page += 1
        time.sleep(random.uniform(pmin, pmax))


def seed_from_csv():
    """把已有 data/st_since2020/*.csv 导入 DB(幂等),使断点续采接着已采数据走。"""
    db = sqlite3.connect(DB_PATH, timeout=60)
    total = 0
    for f in glob.glob(f"{DATA_DIR}/*.csv"):
        with open(f, encoding="utf-8-sig") as fh:
            for x in csv.DictReader(fh):
                if not x.get("post_id"):
                    continue
                def i(v):
                    try: return int(v)
                    except (ValueError, TypeError): return 0
                db.execute("INSERT OR IGNORE INTO posts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    i(x["post_id"]), x.get("stock_code", ""), x.get("stock_name", ""),
                    x.get("title", ""), x.get("author", ""), str(x.get("author_id", "")),
                    x.get("publish_time", ""), i(x.get("read_count") or x.get("reads")),
                    i(x.get("comment_count") or x.get("comments")),
                    i(x.get("forward_count") or x.get("forwards")),
                    str(x.get("bullish_bearish", "")), x.get("url", ""), x.get("crawl_time", "")))
                total += 1
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    db.close()
    print(f"  播种完成:读入 {total} 行,DB 现有 {n} 条(已去重)")


def export_csv():
    db = sqlite3.connect(DB_PATH)
    cols = [c[1] for c in db.execute("PRAGMA table_info(posts)")]
    os.makedirs(DATA_DIR, exist_ok=True)
    for code, name in STOCKS:
        rows = db.execute("SELECT * FROM posts WHERE stock_code=? ORDER BY publish_time", (code,)).fetchall()
        with open(f"{DATA_DIR}/{code}_{name}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(cols); w.writerows(rows)
        print(f"  导出 {name}: {len(rows)} 条")
    db.close()


def main():
    ap = argparse.ArgumentParser(description="ST 股吧采集器(整合版)")
    ap.add_argument("--since", default="2020-01-01")
    ap.add_argument("--threads", type=int, default=3, help="并行股票数(分散访问,别太高)")
    ap.add_argument("--pmin", type=float, default=2.5, help="页间最小延时秒")
    ap.add_argument("--pmax", type=float, default=4.5, help="页间最大延时秒")
    ap.add_argument("--empty-limit", type=int, default=8, help="连续空页多少次判到底/限流")
    ap.add_argument("--export", action="store_true", help="只把 DB 导出为 CSV")
    ap.add_argument("--seed", action="store_true", help="只把已有 CSV 播种进 DB")
    a = ap.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    init_db(DB_PATH).close()
    if a.export:
        export_csv(); return
    if a.seed:
        seed_from_csv(); return
    seed_from_csv()   # 每次开跑前先接住已有数据,断点续采

    print(f"多线程 {a.threads} | 页间 {a.pmin}-{a.pmax}s | 目标 since {a.since}\n", flush=True)
    with ThreadPoolExecutor(max_workers=a.threads) as pool:
        futs = {pool.submit(scrape_stock, c, n, a.since, a.pmin, a.pmax, a.empty_limit): n
                for c, n in STOCKS}
        for fut in as_completed(futs):
            code, name, new, reason = fut.result()
            print(f"  ✅ {name}: +{new} | {reason}", flush=True)
    export_csv()
    db = sqlite3.connect(DB_PATH)
    print(f"\nDB 合计 {db.execute('SELECT COUNT(*) FROM posts').fetchone()[0]} 条", flush=True)


if __name__ == "__main__":
    main()
