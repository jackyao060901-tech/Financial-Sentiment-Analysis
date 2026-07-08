"""雪球(Xueqiu)ST 股讨论帖采集器 —— 本地浏览器版,深爬到 2020。

为什么必须浏览器 + 本地:
  - 雪球讨论页受**阿里云 WAF**保护,`requests` 拿不到(只返回挑战页)。
  - 雪球的"公开搜索接口"虽能绕过 WAF,但**硬性上限 1000 条/只**,到不了 2020(实测)。
  - 真正的全量历史在网页"讨论"里无限下滚才拿得到。用真实浏览器(Playwright)打开个股页
    通过 WAF 的 JS 挑战,再顺着"时间线"接口用 max_id 游标一直往前翻(就是网页下滚的机制),
    不受 1000 条限制,可回溯到 2020 甚至更早。
  - 这需要**住宅 IP + 能联网的浏览器**;在普通电脑(如老师本地)跑,不要在机房/云沙盒跑。

跑法:
  pip install -r requirements.txt
  playwright install chromium        # 本地首次需要
  python xueqiu_scraper.py                     # 采 STOCKS 里 5 只到 2020
  python xueqiu_scraper.py --since 2020-01-01  # 指定回溯日期
  python xueqiu_scraper.py --export            # 只把 DB 导出成 CSV
  python xueqiu_scraper.py --proxy http://ip:port   # 需要时挂代理(如老师的 freeproxy)

特性:SQLite(post_id 主键去重)· 断点续采(接着已有最旧帖继续)· 中断不丢数据(每批入库)。
"""
import os
import re
import csv
import json
import time
import random
import sqlite3
import argparse
import datetime

# 目标股票(纯数字代码, 名称)—— 按需改这里
STOCKS = [
    ("300301", "ST长方"), ("002816", "ST和科"), ("688646", "ST逸飞"),
    ("688076", "ST诺泰"), ("002055", "ST得润"),
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
# 网页无限下滚用的"讨论时间线"接口(浏览器过 WAF 后可用),max_id 游标无限往前翻
TIMELINE = ("https://xueqiu.com/statuses/stock_timeline.json"
            "?symbol_id={symbol}&count=20&source=all")

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts(
    post_id     INTEGER PRIMARY KEY,
    symbol      TEXT, stock_name TEXT,
    title TEXT, text TEXT, truncated INTEGER,
    author TEXT, user_id TEXT, created_at TEXT,
    reply_count INTEGER, like_count INTEGER, retweet_count INTEGER,
    view_count INTEGER, fav_count INTEGER,
    source TEXT, url TEXT, crawl_time TEXT
);
CREATE INDEX IF NOT EXISTS idx_symbol ON posts(symbol);
CREATE INDEX IF NOT EXISTS idx_time   ON posts(created_at);
"""
COLS = ["post_id", "symbol", "stock_name", "title", "text", "truncated", "author",
        "user_id", "created_at", "reply_count", "like_count", "retweet_count",
        "view_count", "fav_count", "source", "url", "crawl_time"]


def prefix(code):
    code = str(code)
    if code.upper().startswith(("SH", "SZ")):
        return code.upper()
    return ("SH" if code.startswith("6") else "SZ") + code


def _dt(ms):
    try:
        return datetime.datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return ""


def _clean(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def parse_post(it, symbol, name):
    """雪球一条帖子 JSON → DB 行。字段依据真实接口返回(已用真实数据核对)。"""
    user = it.get("user") or {}
    return {
        "post_id": it.get("id"),
        "symbol": symbol, "stock_name": name,
        "title": _clean(it.get("title") or ""),
        "text": _clean(it.get("text") or it.get("description") or ""),
        "truncated": 1 if it.get("truncated") else 0,
        "author": user.get("screen_name", ""),
        "user_id": str(user.get("id", "")),
        "created_at": _dt(it.get("created_at")),
        "reply_count": it.get("reply_count") or 0,
        "like_count": it.get("like_count") or 0,
        "retweet_count": it.get("retweet_count") or 0,
        "view_count": it.get("view_count") or 0,
        "fav_count": it.get("fav_count") or 0,
        "source": it.get("source", ""),
        "url": (f"https://xueqiu.com{it.get('target', '')}" if it.get("target")
                else f"https://xueqiu.com/S/{symbol}"),
        "crawl_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def db_connect(path):
    db = sqlite3.connect(path, timeout=60)
    db.executescript(SCHEMA)
    return db


def save_rows(db, rows):
    ph = ",".join(["?"] * len(COLS))
    n = 0
    for r in rows:
        n += db.execute(f"INSERT OR IGNORE INTO posts({','.join(COLS)}) VALUES({ph})",
                        [r[c] for c in COLS]).rowcount
    db.commit()
    return n


def oldest_id(db, symbol):
    """断点续采:已有该股最旧一条的 post_id,作为 max_id 从那继续往前翻。"""
    row = db.execute("SELECT post_id FROM posts WHERE symbol=? ORDER BY created_at ASC LIMIT 1",
                     (symbol,)).fetchone()
    return row[0] if row else ""


def scrape_stock(db, code, name, since, proxy, delay=(1.5, 3.0)):
    """Playwright 过 WAF,再用时间线接口 + max_id 游标翻到 since。需本地/住宅 IP。"""
    from playwright.sync_api import sync_playwright
    symbol = prefix(code)
    max_id = oldest_id(db, symbol)   # 断点续采
    total_new = 0
    with sync_playwright() as p:
        launch = {"headless": True}
        if proxy:
            launch["proxy"] = {"server": proxy}
        browser = p.chromium.launch(**launch)
        ctx = browser.new_context(user_agent=UA, ignore_https_errors=True)
        page = ctx.new_page()
        # 1) 打开个股页,过 WAF(浏览器执行 JS 挑战,拿到 acw_sc__v2 等 cookie)
        page.goto(f"https://xueqiu.com/S/{symbol}", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)
        if max_id:
            print(f"  [{name}] 断点续采,从 max_id={max_id} 继续", flush=True)
        # 2) 用浏览器上下文(带过 WAF 的 cookie)顺着时间线游标往前翻
        empty = 0
        while True:
            url = TIMELINE.format(symbol=symbol) + (f"&max_id={max_id}" if max_id else "")
            resp = page.request.get(url, headers={"Referer": f"https://xueqiu.com/S/{symbol}"})
            try:
                d = resp.json()
            except Exception:
                print(f"  [{name}] 返回非 JSON(WAF 未过/需登录),停"); break
            lst = d.get("list") or []
            if not lst:
                empty += 1
                if empty >= 3:
                    print(f"  [{name}] 无更多帖子(到底),停"); break
                page.wait_for_timeout(3000); continue
            empty = 0
            rows = [parse_post(it, symbol, name) for it in lst]
            total_new += save_rows(db, rows)
            oldest = min((r["created_at"] for r in rows if r["created_at"]), default="")
            print(f"  [{name}] +{len(rows)} 累计新{total_new} 最旧{oldest[:10]}", flush=True)
            max_id = lst[-1].get("id")
            if oldest and oldest[:10] < since:
                print(f"  [{name}] ✅ 已回溯到 {since},完成"); break
            if not max_id:
                break
            page.wait_for_timeout(int(random.uniform(*delay) * 1000))  # 拟人间隔
        browser.close()
    return total_new


def export_csv(db_path, out_dir="data"):
    db = db_connect(db_path)
    os.makedirs(out_dir, exist_ok=True)
    for symbol, name in db.execute("SELECT DISTINCT symbol, stock_name FROM posts").fetchall():
        rows = db.execute(f"SELECT {','.join(COLS)} FROM posts WHERE symbol=? ORDER BY created_at",
                          (symbol,)).fetchall()
        with open(f"{out_dir}/xueqiu_{symbol}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(COLS); w.writerows(rows)
        print(f"  导出 {name}({symbol}): {len(rows)} 条")


def main():
    ap = argparse.ArgumentParser(description="雪球 ST 股讨论帖采集器(本地浏览器版,深爬到2020)")
    ap.add_argument("--db", default="data/xueqiu.db")
    ap.add_argument("--since", default="2020-01-01", help="回溯到的日期")
    ap.add_argument("--proxy", default=None, help="可选代理,如 http://ip:port")
    ap.add_argument("--export", action="store_true", help="只导出 CSV")
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.db) or ".", exist_ok=True)
    if a.export:
        export_csv(a.db); return
    db = db_connect(a.db)
    for code, name in STOCKS:
        print(f"== {name}({code}) 深爬到 {a.since} ==", flush=True)
        try:
            got = scrape_stock(db, code, name, a.since, a.proxy)
            print(f"  -> +{got} 新增", flush=True)
        except Exception as e:
            print(f"  [error] {name}: {type(e).__name__}: {e}", flush=True)
        time.sleep(random.uniform(4, 8))   # 换股歇一下
    export_csv(a.db)
    print(f"\nDB 合计 {db.execute('SELECT COUNT(*) FROM posts').fetchone()[0]} 条", flush=True)


if __name__ == "__main__":
    main()
