"""同花顺个股资讯采集原型(公开 JSON 接口,无需签名/登录)。

背景:
  同花顺的**社区帖子**(t.10jqka.com.cn/guba)是 Vue SPA + 带 md5 签名的接口,
  较难爬(需浏览器或逆向签名),详见 docs/feasibility_report.md。
  但同花顺的**个股资讯(文章)**有一个干净的公开 JSON 接口,直接可取:
      https://news.10jqka.com.cn/tapp/news/push/stock/?page={n}&code={code}
  返回 data.list,每条含 title、digest(摘要正文)、url、ctime(秒级时间戳)、source。

说明:
  - 这里采的是"资讯/文章"(导师原话含"帖子、文章"),不是散户帖子;
    因此没有阅读数/评论数,情绪价值不同于股吧散户帖,但同属可用语料。
  - code 为纯数字代码,如 000001 / 600519,不带交易所前缀。
  - digest 已是较完整的摘要文本,默认即作为 content,无需二次请求详情页。

用法:
  python crawlers/ths_news.py --code 000001 --pages 2
"""
import argparse
import datetime

from common import make_session, polite_get, save_csv, clean_text

API = "https://news.10jqka.com.cn/tapp/news/push/stock/?page={page}&code={code}"
REFERER = "http://t.10jqka.com.cn/guba/{code}/"


def _ts_to_dt(ts):
    try:
        return datetime.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return ""


def parse_page(data, code):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for it in data.get("data", {}).get("list", []):
        rows.append({
            "platform": "ths_news",
            "stock_code": code,
            "post_id": it.get("id") or it.get("seq"),
            "title": clean_text(it.get("title", "")),
            "content": clean_text(it.get("digest") or it.get("short") or ""),
            "author": it.get("source", ""),      # 资讯来源(可能为空)
            "author_id": "",
            "publish_time": _ts_to_dt(it.get("ctime")),
            "read_count": "",                     # 资讯无阅读/评论数
            "comment_count": "",
            "forward_count": "",
            "bullish_bearish": "",
            "has_pic": bool(it.get("picUrl")),
            "has_video": "",
            "url": it.get("url", ""),
            "crawl_time": now,
        })
    return rows


def crawl(code, pages=2):
    session = make_session()
    all_rows = []
    for pg in range(1, pages + 1):
        r = polite_get(session, API.format(page=pg, code=code),
                       referer=REFERER.format(code=code))
        if r.status_code != 200:
            print(f"[warn] 第 {pg} 页 HTTP {r.status_code},跳过")
            continue
        try:
            data = r.json()
        except ValueError:
            print(f"[warn] 第 {pg} 页非 JSON,跳过")
            continue
        rows = parse_page(data, code)
        print(f"[第 {pg} 页] 解析到 {len(rows)} 条资讯")
        all_rows.extend(rows)
    return all_rows


def main():
    ap = argparse.ArgumentParser(description="同花顺个股资讯采集原型")
    ap.add_argument("--code", default="000001", help="纯数字代码,如 000001 / 600519")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows = crawl(a.code, a.pages)
    out = a.out or f"data/samples/ths_news_{a.code}_sample.csv"
    save_csv(rows, out)
    print(f"已保存 {len(rows)} 条 -> {out}")


if __name__ == "__main__":
    main()
