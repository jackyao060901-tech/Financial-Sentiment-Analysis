"""淘股吧采集原型(传统站点,requests 可直接爬)。

原理:
  个股页 https://taoguba.com.cn/quotes/{symbol}(symbol 形如 sz000001)里,
  `class="related-subject"` 区是该股相关讨论帖,给出标题 + 文章链接
  (形如 https://www.tgb.cn/a/{id})。
  文章页可取:标题(article-tittle)、正文(article-text p_coten)、
  以及 article-data 区的 作者 / 发表时间(带年份)/ 浏览数 / 评论数。

注意:
  - `www.taoguba.com.cn` 证书异常,用主域 `taoguba.com.cn`;文章用 `www.tgb.cn`。
  - 个股页每次约给出数条相关帖,数据量不如股吧/新浪,作补充数据源。

用法:
  python crawlers/taoguba.py --symbol sz000001
"""
import re
import argparse
import datetime

from common import make_session, polite_get, save_csv, clean_text

STOCK_URL = "https://taoguba.com.cn/quotes/{symbol}"

RE_SUBJECT = re.compile(
    r'class="related-subject"[^>]*>\s*<a href="(https://www\.tgb\.cn/a/([^"#]+))[^"]*"[^>]*>([^<]+)</a>')
RE_TITLE = re.compile(r'class="article-tittle"[^>]*>(.*?)</', re.S)
RE_BODY = re.compile(r'class="article-text p_coten"[^>]*>(.*?)</div>', re.S)
RE_DATA = re.compile(r'class="article-data"[^>]*>(.*?)</div>', re.S)
RE_TIME = re.compile(r'(20\d\d-\d\d-\d\d \d\d:\d\d)')
RE_READ = re.compile(r'浏览\s*(\d+)')
RE_COMMENT = re.compile(r'评论\s*(\d+)')


def fetch_article(session, url, pid, symbol):
    """请求文章页,抽取标题/正文/作者/时间/浏览/评论。"""
    r = polite_get(session, url, referer="https://taoguba.com.cn/")
    d = r.text
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mt, mb, md = RE_TITLE.search(d), RE_BODY.search(d), RE_DATA.search(d)
    data_txt = clean_text(md.group(1)) if md else ""
    # article-data 区形如:"作者名 淘股吧原创 2026-06-29 20:47 | 浏览 143 | 评论 0 ..."
    author = data_txt.split(" ")[0] if data_txt else ""
    mtime, mread, mcomment = RE_TIME.search(data_txt), RE_READ.search(data_txt), RE_COMMENT.search(data_txt)
    return {
        "platform": "taoguba",
        "stock_code": symbol,
        "post_id": pid,
        "title": clean_text(mt.group(1)) if mt else "",
        "content": clean_text(mb.group(1)) if mb else "",
        "author": author,
        "author_id": "",
        "publish_time": mtime.group(1) if mtime else "",
        "read_count": mread.group(1) if mread else "",
        "comment_count": mcomment.group(1) if mcomment else "",
        "forward_count": "",
        "bullish_bearish": "",
        "has_pic": "",
        "has_video": "",
        "url": url,
        "crawl_time": now,
    }


def crawl(symbol, limit=8):
    session = make_session()
    r = polite_get(session, STOCK_URL.format(symbol=symbol), referer="https://taoguba.com.cn/")
    subjects = RE_SUBJECT.findall(r.text)
    # 去重(按文章 id)
    seen, uniq = set(), []
    for url, pid, title in subjects:
        if pid not in seen:
            seen.add(pid)
            uniq.append((url, pid))
    print(f"[个股页] 找到 {len(uniq)} 条相关讨论帖")
    rows = []
    for url, pid in uniq[:limit]:
        rows.append(fetch_article(session, url, pid, symbol))
    return rows


def main():
    ap = argparse.ArgumentParser(description="淘股吧采集原型")
    ap.add_argument("--symbol", default="sz000001", help="交易所前缀+代码,如 sz000001")
    ap.add_argument("--limit", type=int, default=8, help="最多抓多少篇文章")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows = crawl(a.symbol, a.limit)
    out = a.out or f"data/samples/taoguba_{a.symbol}_sample.csv"
    save_csv(rows, out)
    print(f"已保存 {len(rows)} 条 -> {out}")


if __name__ == "__main__":
    main()
