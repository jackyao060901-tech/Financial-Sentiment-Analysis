"""腾讯股票个股资讯/研报采集原型(公开接口,无需登录/签名)。

接口:
  https://web.ifzq.gtimg.cn/appstock/news/info/search?symbol={sz/sh+code}&page={n}&n={num}&type={t}
  返回 data.data 列表,含 id/title/time/url/src(来源)/typeStr。
  type:1=研报,2/3=新闻。无需登录、无需签名。

说明:
  - 与富途一样,列表**仅标题、无正文摘要**(summary 字段为空,正文需再解析 gu.qq.com SPA 详情页),
    因此归入"资讯类原型",默认不纳入需带正文的样本集。
  - symbol 需交易所前缀,如 sz000001 / sh600519。

用法:
  python crawlers/tencent_news.py --symbol sz000001 --type 1
"""
import argparse
import datetime

from common import make_session, polite_get, save_csv, clean_text

API = ("https://web.ifzq.gtimg.cn/appstock/news/info/search"
       "?symbol={symbol}&page={page}&n={num}&type={type}")


def crawl(symbol, num=15, ntype=1, pages=1):
    session = make_session()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for pg in range(1, pages + 1):
        url = API.format(symbol=symbol, page=pg, num=num, type=ntype)
        r = polite_get(session, url, referer="https://gu.qq.com/")
        try:
            lst = r.json().get("data", {}).get("data", []) or []
        except ValueError:
            print("[warn] 非 JSON")
            continue
        print(f"[第 {pg} 页] 解析到 {len(lst)} 条")
        for it in lst:
            rows.append({
                "platform": "tencent_news",
                "stock_code": symbol,
                "post_id": it.get("id"),
                "title": clean_text(it.get("title", "")),
                "content": clean_text(it.get("summary") or ""),  # 通常为空
                "author": it.get("src", ""),
                "author_id": "",
                "publish_time": it.get("time", ""),
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
    ap = argparse.ArgumentParser(description="腾讯股票个股资讯采集原型")
    ap.add_argument("--symbol", default="sz000001", help="交易所前缀+代码,如 sz000001")
    ap.add_argument("--type", type=int, default=1, help="1=研报,2/3=新闻")
    ap.add_argument("--num", type=int, default=15)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows = crawl(a.symbol, a.num, a.type)
    out = a.out or f"data/samples/tencent_news_{a.symbol}_sample.csv"
    save_csv(rows, out)
    print(f"已保存 {len(rows)} 条 -> {out}")


if __name__ == "__main__":
    main()
