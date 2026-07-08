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

import requests

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


def _extract_lists(obj, bag):
    """从任意 JSON 里递归掏出看起来像"帖子列表"的数组(元素含 created_at)。"""
    if isinstance(obj, dict):
        for v in obj.values():
            _extract_lists(v, bag)
    elif isinstance(obj, list):
        if obj and isinstance(obj[0], dict) and ("created_at" in obj[0] or "id" in obj[0]):
            bag.append(obj)
        for v in obj:
            _extract_lists(v, bag)


def scrape_stock(db, code, name, since, proxy, max_minutes=30, delay=(1.2, 2.5)):
    """浏览器抓取(最稳方式):打开个股讨论页过 WAF,**滚动页面触发无限加载**,
    同时**拦截页面自己发出的所有 XHR 响应**,从中掏出帖子入库,直到回溯到 since。
    这样不依赖猜某个接口——网页能滚到哪年,就抓到哪年。需本地/住宅 IP。
    另外也顺带用时间线游标接口试翻(双保险)。
    """
    from playwright.sync_api import sync_playwright
    symbol = prefix(code)
    total_new = [0]
    oldest_seen = ["9999-99-99"]

    def ingest(items):
        rows = [parse_post(it, symbol, name) for it in items
                if isinstance(it, dict) and it.get("id") and it.get("created_at")]
        if rows:
            total_new[0] += save_rows(db, rows)
            o = min((r["created_at"] for r in rows if r["created_at"]), default="")
            if o and o < oldest_seen[0]:
                oldest_seen[0] = o

    with sync_playwright() as p:
        launch = {"headless": True}
        if proxy:
            launch["proxy"] = {"server": proxy}
        browser = p.chromium.launch(**launch)
        ctx = browser.new_context(user_agent=UA, ignore_https_errors=True)
        page = ctx.new_page()

        # 拦截:任何 xueqiu 的帖子类 XHR 响应,都掏出列表入库
        def on_response(resp):
            u = resp.url
            if "xueqiu.com" in u and any(k in u for k in ("timeline", "search/status", "/statuses/")):
                try:
                    bag = []
                    _extract_lists(resp.json(), bag)
                    for lst in bag:
                        ingest(lst)
                except Exception:
                    pass
        page.on("response", on_response)

        # 1) 打开个股讨论页,过 WAF
        page.goto(f"https://xueqiu.com/S/{symbol}", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(5000)

        # 2) 一边用时间线游标接口翻(快),一边滚动页面(兜底);谁能往前走都收下
        deadline = time.time() + max_minutes * 60
        max_id = oldest_id(db, symbol)
        stagnant = 0
        while time.time() < deadline:
            before = total_new[0]
            oldest_before = oldest_seen[0]
            # (a) 游标接口
            try:
                url = TIMELINE.format(symbol=symbol) + (f"&max_id={max_id}" if max_id else "")
                d = page.request.get(url, headers={"Referer": f"https://xueqiu.com/S/{symbol}"}).json()
                lst = d.get("list") or []
                if lst:
                    ingest(lst)
                    max_id = lst[-1].get("id") or max_id
            except Exception:
                pass
            # (b) 滚动页面,触发它自己的无限加载(响应被 on_response 收走)
            try:
                page.mouse.wheel(0, 24000)
            except Exception:
                pass
            page.wait_for_timeout(int(random.uniform(*delay) * 1000))
            print(f"  [{name}] 累计新{total_new[0]} 最旧{oldest_seen[0][:10]}", flush=True)
            if oldest_seen[0] != "9999-99-99" and oldest_seen[0][:10] < since:
                print(f"  [{name}] ✅ 已回溯到 {since},完成"); break
            # 连续没有新数据 & 最旧没变早 → 到底/被限,停
            if total_new[0] == before and oldest_seen[0] == oldest_before:
                stagnant += 1
                if stagnant >= 6:
                    print(f"  [{name}] 连续无进展(到底/被限),停在 {oldest_seen[0][:10]}"); break
            else:
                stagnant = 0
        browser.close()
    return total_new[0], oldest_seen[0][:10]


def quick_test(code, since, proxy):
    """本地自测:对一只股票跑最多 90 秒,报告能回溯到哪天——用来先确认能不能到 2020。"""
    import tempfile
    name = dict(STOCKS).get(code, code)
    db = db_connect(os.path.join(tempfile.gettempdir(), "xq_test.db"))
    print(f"== 自测 {name}({code}):跑 ~90 秒看能回溯到哪天 ==")
    new, oldest = scrape_stock(db, code, name, since, proxy, max_minutes=1.5)
    print(f"\n自测结果:{name} 采到 {new} 条,最旧 {oldest}")
    if oldest <= since:
        print(f"✅ 能翻过 {since} —— 这套可以爬到 2020,放心长跑。")
    elif oldest < "2023-01-01":
        print(f"🟡 翻过了 2023(到 {oldest}),说明能突破 1000 条上限、在往 2020 走 —— 可长跑。")
    else:
        print(f"❌ 只到 {oldest},没能突破近端 —— 浏览器也被限在 ~1000 条。\n"
              f"   退路:①用登录后的雪球 cookie;②确认该股在雪球是否真有 2020 的帖(可能本就没有)。")


API_URL = ("https://api.xueqiu.com/query/v1/symbol/search/status.json"
           "?symbol={symbol}&count=20&source=all&sort=time&page={page}")


def fetch_api(db, code, name, max_pages=60, delay=(1.0, 2.0)):
    """API 模式:绕过 WAF(csrf 拿 token)取"前 ~1000 条"(雪球硬性上限)。
    任意机器可跑(含云沙盒),无需浏览器。到不了 2020(平台限制),用于"先拿近期"。
    """
    symbol = prefix(code)
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Referer": f"https://xueqiu.com/S/{symbol}"})
    s.get("https://xueqiu.com/service/csrf?api=/statuses/search.json", timeout=15)  # 拿 token
    total, oldest = 0, ""
    for page in range(1, max_pages + 1):
        try:
            d = s.get(API_URL.format(symbol=symbol, page=page), timeout=15).json()
        except Exception as e:
            print(f"  [{name}] 第{page}页 异常 {type(e).__name__},停"); break
        lst = d.get("list") or []
        if not lst:
            break
        rows = [parse_post(it, symbol, name) for it in lst]
        total += save_rows(db, rows)
        oldest = min((r["created_at"] for r in rows if r["created_at"]), default=oldest)
        if page % 10 == 0 or page == 1:
            print(f"  [{name}] 第{page}页 累计新{total} 最旧{oldest[:10]}", flush=True)
        if page >= (d.get("maxPage") or max_pages):
            break
        time.sleep(random.uniform(*delay))
    return total, oldest[:10]


# CSV 导出列顺序:导师定的重要字段(post_id/user_id/标题/正文/评论)排最前
EXPORT_ORDER = ["post_id", "user_id", "author", "created_at", "title", "text",
                "reply_count", "like_count", "retweet_count", "view_count",
                "symbol", "stock_name", "source", "url", "truncated", "fav_count", "crawl_time"]


def export_csv(db_path, out_dir="data"):
    db = db_connect(db_path)
    os.makedirs(out_dir, exist_ok=True)
    for symbol, name in db.execute("SELECT DISTINCT symbol, stock_name FROM posts").fetchall():
        rows = db.execute(f"SELECT {','.join(EXPORT_ORDER)} FROM posts WHERE symbol=? ORDER BY created_at",
                          (symbol,)).fetchall()
        with open(f"{out_dir}/xueqiu_{symbol}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(EXPORT_ORDER); w.writerows(rows)
        print(f"  导出 {name}({symbol}): {len(rows)} 条")


def main():
    ap = argparse.ArgumentParser(description="雪球 ST 股讨论帖采集器(本地浏览器版,深爬到2020)")
    ap.add_argument("--db", default="data/xueqiu.db")
    ap.add_argument("--since", default="2020-01-01", help="回溯到的日期")
    ap.add_argument("--proxy", default=None, help="可选代理,如 http://ip:port")
    ap.add_argument("--export", action="store_true", help="只导出 CSV")
    ap.add_argument("--test", metavar="CODE", default=None,
                    help="本地自测:先跑一只股票~90秒,看能否翻过2023到2020(强烈建议长跑前先跑)")
    ap.add_argument("--api", action="store_true",
                    help="API 模式:取前~1000条(雪球硬顶,到不了2020),任意机器可跑,无需浏览器")
    a = ap.parse_args()

    os.makedirs(os.path.dirname(a.db) or ".", exist_ok=True)
    if a.export:
        export_csv(a.db, os.path.dirname(a.db) or "data"); return
    if a.test:
        quick_test(a.test, a.since, a.proxy); return
    db = db_connect(a.db)
    for code, name in STOCKS:
        try:
            if a.api:
                print(f"== {name}({code}) API 取前~1000条 ==", flush=True)
                got, oldest = fetch_api(db, code, name)
            else:
                print(f"== {name}({code}) 浏览器深爬到 {a.since} ==", flush=True)
                got, oldest = scrape_stock(db, code, name, a.since, a.proxy)
            print(f"  -> +{got} 新增,最旧 {oldest}", flush=True)
        except Exception as e:
            print(f"  [error] {name}: {type(e).__name__}: {e}", flush=True)
        time.sleep(random.uniform(4, 8))   # 换股歇一下
    export_csv(a.db)
    print(f"\nDB 合计 {db.execute('SELECT COUNT(*) FROM posts').fetchone()[0]} 条", flush=True)


if __name__ == "__main__":
    main()
