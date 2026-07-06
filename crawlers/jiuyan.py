"""韭研公社采集原型(游资/散户研究社区,SSR 内嵌数据,无需登录)。

背景:
  韭研公社(jiuyangongshe.com)是活跃的**游资/短线研究社区**,帖子多为对个股/题材的
  深度研究与盘面解读——**研究价值高**(真散户/游资观点,非新闻转载)。

原理:
  - 首页 HTML 里有文章链接 `/a/{id}`。
  - 文章页 `www.jiuyangongshe.com/a/{id}` 是 Nuxt SSR,数据写在内嵌 `window.__NUXT__` 里,
    单篇一页,可干净取到 `title` / `content`(完整正文)/ `create_time`。无需登录。

说明:
  - 这是**综合(市场级)信息流**,非按单只股票过滤(stock_code 留空/标"综合");
    帖子本身常在正文里点名个股与题材,后续可按需从正文抽取标的。
  - Nuxt 状态须按 UTF-8 读取(`r.encoding="utf-8"`)。

用法:
  python crawlers/jiuyan.py --limit 15
"""
import re
import json
import argparse
import datetime

from common import make_session, polite_get, save_csv, clean_text

BASE = "https://www.jiuyangongshe.com"


def _unescape(s):
    try:
        return json.loads('"' + s + '"')
    except json.JSONDecodeError:
        return s


def _field(seg, key):
    m = re.search(r'%s:"((?:[^"\\]|\\.)*?)"' % key, seg)
    return _unescape(m.group(1)) if m else ""


def list_article_ids(session, limit):
    r = polite_get(session, BASE + "/", referer=BASE + "/")
    ids = list(dict.fromkeys(re.findall(r'/a/([0-9a-z]+)"', r.text)))
    return ids[:limit]


def fetch_article(session, aid):
    r = polite_get(session, f"{BASE}/a/{aid}", referer=BASE + "/")
    r.encoding = "utf-8"
    seg = r.text[r.text.find("window.__NUXT__"):]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    title = clean_text(re.sub(r"<[^>]+>", "", _field(seg, "title")))
    content = clean_text(_field(seg, "content"))
    author = clean_text(_field(seg, "nickname") or _field(seg, "name"))
    ctime = _field(seg, "create_time")
    return {
        "platform": "jiuyan",
        "stock_code": "",          # 综合信息流,非按单股过滤
        "post_id": aid,
        "title": title,
        "content": content,
        "author": author,
        "author_id": "",
        "publish_time": ctime,
        "read_count": "",
        "comment_count": "",
        "forward_count": "",
        "bullish_bearish": "",
        "has_pic": "",
        "has_video": "",
        "url": f"{BASE}/a/{aid}",
        "crawl_time": now,
    }


def crawl(limit=15):
    session = make_session()
    ids = list_article_ids(session, limit)
    print(f"[首页] 取到 {len(ids)} 篇文章链接")
    rows = []
    for aid in ids:
        row = fetch_article(session, aid)
        if row["title"]:
            rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description="韭研公社采集原型")
    ap.add_argument("--limit", type=int, default=15, help="抓取文章数")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows = crawl(a.limit)
    out = a.out or "data/samples/jiuyan_sample.csv"
    save_csv(rows, out)
    print(f"已保存 {len(rows)} 条 -> {out}")


if __name__ == "__main__":
    main()
