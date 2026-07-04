"""雪球采集原型(难度高,已如实记录现状)。

侦察结论:
  雪球的数据接口(如 /query/v1/symbol/search/status)受**阿里云 WAF + JS 挑战**保护。
  实测:用 requests 先访问首页拿到 cookie(acw_tc / s / u 等)再请求接口,
  返回的仍是 WAF 挑战页(内容里含 aliyun_waf / _waf_ 等字段)而不是数据,
  所以**纯 requests 方案不可行**。

可行路径:
  用真实浏览器(本环境已预装 Chromium,可用 Playwright)先加载页面通过 JS 挑战,
  拿到有效 cookie 后再在同一浏览器上下文里请求接口,或直接解析页面 DOM。
  下面 fetch_via_browser 就是这条思路的原型。

注意:
  - 首次使用需要:pip install playwright(Chromium 已装,勿再 playwright install)。
  - 雪球反爬较严,务必控制频率、别高频请求,否则容易被封 IP。
  - 帖子正文在 text 字段里是 HTML,已做简单去标签。

用法:
  python crawlers/xueqiu.py --symbol SZ000001 --pages 1
"""
import re
import argparse
import datetime

from common import save_csv

# type=11 为讨论帖;symbol 形如 SZ000001 / SH600519
API = ("https://xueqiu.com/query/v1/symbol/search/status"
       "?count=20&comment=0&symbol={symbol}&hl=0&source=all"
       "&sort=&page={page}&q=&type=11")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def _ms_to_dt(ms):
    if not ms:
        return ""
    try:
        return datetime.datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return ""


def _map_item(it, symbol, now):
    user = it.get("user") or {}
    text = _strip_html(it.get("text", ""))
    return {
        "platform": "xueqiu",
        "stock_code": symbol,
        "post_id": it.get("id"),
        "title": it.get("title") or text[:40],
        "content": text,
        "author": user.get("screen_name", ""),
        "author_id": user.get("id", ""),
        "publish_time": _ms_to_dt(it.get("created_at")),
        "read_count": it.get("view_count", ""),
        "comment_count": it.get("reply_count", ""),
        "forward_count": it.get("retweet_count", ""),
        "bullish_bearish": "",
        "has_pic": bool(it.get("pic")),
        "has_video": "",
        "url": "https://xueqiu.com" + it.get("target", ""),
        "crawl_time": now,
    }


def fetch_via_browser(symbol="SZ000001", pages=1):
    """用 Playwright 打开雪球通过 WAF,再请求接口取数据。"""
    from playwright.sync_api import sync_playwright

    rows = []
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA)
        page = ctx.new_page()
        # 先访问首页,让浏览器执行 JS 挑战、拿到有效 cookie
        page.goto("https://xueqiu.com/", wait_until="networkidle", timeout=30000)
        for pg in range(1, pages + 1):
            resp = page.request.get(
                API.format(symbol=symbol, page=pg),
                headers={"Referer": "https://xueqiu.com/"},
            )
            try:
                data = resp.json()
            except Exception:
                print(f"[warn] 第 {pg} 页返回非 JSON(可能仍被 WAF 拦),已跳过")
                continue
            items = data.get("list", [])
            print(f"[第 {pg} 页] 取到 {len(items)} 条")
            for it in items:
                rows.append(_map_item(it, symbol, now))
        browser.close()
    return rows


def main():
    ap = argparse.ArgumentParser(description="雪球采集原型(需 Playwright)")
    ap.add_argument("--symbol", default="SZ000001", help="如 SZ000001 / SH600519")
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    try:
        rows = fetch_via_browser(a.symbol, a.pages)
    except ImportError:
        print("需要 Playwright:pip install playwright(Chromium 已预装,勿再 playwright install)")
        return
    out = a.out or f"data/samples/xueqiu_{a.symbol}_sample.csv"
    save_csv(rows, out)
    print(f"已保存 {len(rows)} 条 -> {out}")


if __name__ == "__main__":
    main()
