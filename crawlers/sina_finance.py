"""新浪财经股吧采集原型(可用 requests 直接爬,无需登录/token)。

原理:
  股吧列表页 http://guba.sina.com.cn/?s=bar&name={symbol}&page={n}
  是 **GBK 编码的静态 HTML**,帖子在一个表格里,每个 <tr> 一条:
      阅读数 | 评论数 | 标题(链接) | 作者 | 时间
  标题链接形如 /?s=thread&tid={tid}&bid={bid},class 含 linkblack。
  正文在详情页 http://guba.sina.com.cn/?s=thread&tid=&bid= 的 id="thread_content" 里。

注意:
  - symbol 形如 sz000001 / sh600519(交易所前缀 + 代码)。
  - 列表页时间只有 "MM月DD日"(不带年份),原样保留、不臆造年份。
  - 反爬弱,带常规 UA 即可;仍按 common.polite_get 控制频率。

用法:
  python crawlers/sina_finance.py --symbol sz000001 --pages 2
  python crawlers/sina_finance.py --symbol sh600519 --pages 1 --with-body
"""
import re
import argparse
import datetime

from common import make_session, polite_get, save_csv, clean_text

BASE = "http://guba.sina.com.cn"
LIST_URL = BASE + "/?s=bar&name={symbol}&page={page}"

# 单条帖子(一个 <tr>)里各字段的正则
RE_TITLE = re.compile(
    r'/\?s=thread&tid=(\d+)&bid=(\d+)"[^>]*class="[^"]*linkblack[^"]*"[^>]*>(.*?)</a>', re.S)
RE_REDS = re.compile(r'<span class="red">(\d+)</span>')
RE_AUTHOR = re.compile(r"class=\"author\"><a href='/u/(\d+)'[^>]*>(.*?)</a>", re.S)
RE_TIME = re.compile(r'<td>\s*([^<]*?[月日:][^<]*?)\s*</td>')


def parse_page(html_text, symbol):
    """把一页列表 HTML 解析成统一字段的行。"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    # 按 <tr 切块,只保留含帖子标题链接的行
    for block in html_text.split("<tr"):
        mt = RE_TITLE.search(block)
        if not mt:
            continue
        tid, bid, title = mt.group(1), mt.group(2), clean_text(mt.group(3))
        reds = RE_REDS.findall(block)          # [阅读, 评论]
        ma = RE_AUTHOR.search(block)
        mtime = RE_TIME.search(block)
        rows.append({
            "platform": "sina_guba",
            "stock_code": symbol,
            "post_id": tid,
            "title": title,
            "content": "",
            "author": clean_text(ma.group(2)) if ma else "",
            "author_id": ma.group(1) if ma else "",
            "publish_time": mtime.group(1).strip() if mtime else "",  # 仅"MM月DD日",不带年
            "read_count": reds[0] if len(reds) > 0 else "",
            "comment_count": reds[1] if len(reds) > 1 else "",
            "forward_count": "",
            "bullish_bearish": "",
            "has_pic": "",
            "has_video": "",
            "url": f"{BASE}/?s=thread&tid={tid}&bid={bid}",
            "crawl_time": now,
        })
    return rows


def fetch_body(session, url):
    """详情页正文在 id="thread_content" 容器里。"""
    r = polite_get(session, url, referer=BASE + "/")
    r.encoding = "gbk"
    m = re.search(r'id="thread_content"[^>]*>(.*?)</div>', r.text, re.S)
    return clean_text(m.group(1)) if m else ""


def crawl(symbol, pages=2, with_body=False):
    session = make_session()
    all_rows = []
    for pg in range(1, pages + 1):
        url = LIST_URL.format(symbol=symbol, page=pg)
        r = polite_get(session, url, referer=BASE + "/")
        r.encoding = "gbk"  # 新浪股吧是 GBK
        if r.status_code != 200:
            print(f"[warn] 第 {pg} 页 HTTP {r.status_code},跳过")
            continue
        rows = parse_page(r.text, symbol)
        print(f"[第 {pg} 页] 解析到 {len(rows)} 条帖子")
        if with_body:
            for row in rows:
                row["content"] = fetch_body(session, row["url"])
        all_rows.extend(rows)
    return all_rows


def main():
    ap = argparse.ArgumentParser(description="新浪财经股吧采集原型")
    ap.add_argument("--symbol", default="sz000001", help="交易所前缀+代码,如 sz000001 / sh600519")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--with-body", action="store_true", help="是否额外抓正文(慢)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows = crawl(a.symbol, a.pages, a.with_body)
    out = a.out or f"data/samples/sina_{a.symbol}_sample.csv"
    save_csv(rows, out)
    print(f"已保存 {len(rows)} 条 -> {out}")


if __name__ == "__main__":
    main()
