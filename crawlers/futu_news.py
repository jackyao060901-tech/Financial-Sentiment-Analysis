"""富途牛牛个股资讯采集原型(从页面内嵌状态取数,无需登录)。

原理:
  个股页 https://www.futunn.com/stock/{code}-{MKT}(MKT 为 SZ/SH)是 Vue SPA,
  但服务端把首屏数据写进了内嵌的 `window.__INITIAL_STATE__ = {...}`,
  其中 `stock_news.list` 就是该股资讯列表,含 id/title/time/url/source/abstract。
  → 无需签名、无需登录,解析内嵌 JSON 即可。

说明:
  - 这是**资讯聚合**(来源如"证券之星"等),非富途社区散户帖;社区帖需登录/签名接口,暂缓。
  - code 为纯数字,MKT 由代码推断(6 开头=SH,否则 SZ)。

用法:
  python crawlers/futu_news.py --code 000001
"""
import re
import json
import argparse
import datetime

from common import make_session, polite_get, save_csv, clean_text

STOCK_URL = "https://www.futunn.com/stock/{code}-{mkt}"


def _market(code):
    return "SH" if code.startswith("6") else "SZ"


def _extract_initial(html):
    m = (re.search(r'__INITIAL_STATE__\s*=\s*(\{.+?\})\s*;?\s*</script>', html, re.S)
         or re.search(r'__INITIAL_STATE__\s*=\s*(\{.+)', html))
    if not m:
        return None
    raw = m.group(1)
    depth = 0
    for i, c in enumerate(raw):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _ts(v):
    try:
        return datetime.datetime.fromtimestamp(int(v)).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return ""


def crawl(code):
    session = make_session()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    url = STOCK_URL.format(code=code, mkt=_market(code))
    r = polite_get(session, url, referer="https://www.futunn.com/")
    data = _extract_initial(r.text)
    if not data:
        print("[warn] 未取到内嵌 __INITIAL_STATE__")
        return []
    lst = (data.get("stock_news", {}) or {}).get("list", []) or []
    print(f"[内嵌] 解析到 {len(lst)} 条资讯")
    rows = []
    for it in lst:
        rows.append({
            "platform": "futu_news",
            "stock_code": code,
            "post_id": it.get("id"),
            "title": clean_text(it.get("title", "")),
            "content": clean_text(it.get("abstract", "")),
            "author": it.get("source", ""),
            "author_id": "",
            "publish_time": _ts(it.get("time")),
            "read_count": "",
            "comment_count": "",
            "forward_count": "",
            "bullish_bearish": "",
            "has_pic": "",
            "has_video": "",
            "url": it.get("url", ""),
            "crawl_time": now,
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description="富途牛牛个股资讯采集原型")
    ap.add_argument("--code", default="000001", help="纯数字代码,如 000001 / 600519")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows = crawl(a.code)
    out = a.out or f"data/samples/futu_news_{a.code}_sample.csv"
    save_csv(rows, out)
    print(f"已保存 {len(rows)} 条 -> {out}")


if __name__ == "__main__":
    main()
