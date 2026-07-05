"""东方财富个股新闻采集原型(公开 JSON 接口 + 详情页正文)。

背景:
  东方财富除了「股吧」(散户帖子,见 eastmoney_guba.py),还有「个股新闻」(资讯文章)。
  列表接口:
    https://np-listapi.eastmoney.com/comm/web/getListInfo
      ?client=web&biz=web_news&mTypeAndCode={mkt}.{code}&count={n}&type=1&order=1
  返回 data.list,每条含 Art_Title / Art_ShowTime / Art_Url。
  正文在详情页 Art_Url 的 id="ContentBody" 容器里。

说明:
  - mTypeAndCode 需市场前缀:沪市(6 开头)=1,深市=0,例:1.600519 / 0.000001。
  - 这是「资讯/文章」,非散户帖子,无阅读/评论数;与股吧互补。

用法:
  python crawlers/eastmoney_news.py --code 000001 --count 10 --with-body
"""
import re
import argparse
import datetime

from common import make_session, polite_get, save_csv, clean_text

API = ("https://np-listapi.eastmoney.com/comm/web/getListInfo"
       "?client=web&biz=web_news&mTypeAndCode={mkt}.{code}&count={count}&type=1&order=1")
REFERER = "https://so.eastmoney.com/"


def market_prefix(code):
    """沪市(6/68 开头)=1,其余(深市/创业板)=0。"""
    return "1" if code.startswith("6") else "0"


def fetch_body(session, url):
    r = polite_get(session, url, referer="https://finance.eastmoney.com/")
    r.encoding = "utf-8"
    m = re.search(r'id="ContentBody"[^>]*>(.*?)</div>', r.text, re.S)
    return clean_text(m.group(1)) if m else ""


def crawl(code, count=10, with_body=False):
    session = make_session()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    url = API.format(mkt=market_prefix(code), code=code, count=count)
    r = polite_get(session, url, referer=REFERER)
    try:
        lst = r.json().get("data", {}).get("list", [])
    except ValueError:
        print("[warn] 接口返回非 JSON")
        return []
    print(f"[列表] 取到 {len(lst)} 条新闻")
    rows = []
    for it in lst:
        row = {
            "platform": "eastmoney_news",
            "stock_code": code,
            "post_id": it.get("Art_Code"),
            "title": clean_text(it.get("Art_Title", "")),
            "content": "",
            "author": "",
            "author_id": "",
            "publish_time": it.get("Art_ShowTime", ""),
            "read_count": "",
            "comment_count": "",
            "forward_count": "",
            "bullish_bearish": "",
            "has_pic": "",
            "has_video": "",
            "url": it.get("Art_Url", ""),
            "crawl_time": now,
        }
        if with_body and row["url"]:
            row["content"] = fetch_body(session, row["url"])
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description="东方财富个股新闻采集原型")
    ap.add_argument("--code", default="000001", help="纯数字代码,如 000001 / 600519")
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--with-body", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows = crawl(a.code, a.count, a.with_body)
    out = a.out or f"data/samples/eastmoney_news_{a.code}_sample.csv"
    save_csv(rows, out)
    print(f"已保存 {len(rows)} 条 -> {out}")


if __name__ == "__main__":
    main()
