"""东方财富股吧采集原型(最成熟、最推荐的一条路)。

原理:
  列表页 https://guba.eastmoney.com/list,{code}.html 的静态 HTML 里,
  内嵌了一段 `var article_list = { ... }` 的 JSON,每页约 80 条帖子,
  字段齐全、发帖时间带完整年份,无需登录、无需 token。
  分页:第 1 页是 list,{code}.html,第 n 页是 list,{code}_{n}.html。
  正文:列表 JSON 里没有正文,需要额外请求详情页
        /news,{code},{post_id}.html 才能拿到(默认不取,加 --with-body 才取)。

用法:
  python crawlers/eastmoney_guba.py --code 000001 --pages 3
  python crawlers/eastmoney_guba.py --code 600519 --pages 2 --with-body
"""
import re
import html
import json
import argparse
import datetime

from common import make_session, polite_get, save_csv

LIST_URL = "https://guba.eastmoney.com/list,{code}{page}.html"
BASE = "https://guba.eastmoney.com"


def _extract_article_list(html):
    """从列表页 HTML 中抠出 `var article_list = {...}` 的 JSON。

    用大括号配平来定位 JSON 结束位置,比正则更稳(正文里可能有各种符号)。
    """
    idx = html.find("var article_list")
    if idx == -1:
        return None
    start = html.find("{", idx)
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(html)):
        c = html[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def parse_page(html, code):
    """把一页的 HTML 解析成统一字段的行列表。"""
    data = _extract_article_list(html)
    if not data:
        return []
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for p in data.get("re", []):
        pid = p.get("post_id")
        rows.append({
            "platform": "eastmoney_guba",
            "stock_code": code,
            "post_id": pid,
            "title": p.get("post_title", ""),
            "content": "",  # 正文默认留空,--with-body 时填充
            "author": p.get("user_nickname", ""),
            "author_id": p.get("user_id", ""),
            "publish_time": p.get("post_publish_time", ""),
            "read_count": p.get("post_click_count", ""),
            "comment_count": p.get("post_comment_count", ""),
            "forward_count": p.get("post_forward_count", ""),
            "bullish_bearish": p.get("bullish_bearish", ""),
            "has_pic": p.get("post_has_pic", ""),
            "has_video": p.get("post_has_video", ""),
            "url": f"{BASE}/news,{code},{pid}.html",
            "crawl_time": now,
        })
    return rows


def _clean_html(raw):
    """去 HTML 标签、解码 HTML 实体(&nbsp; &gt; 等)、压缩空白,得到纯文本正文。

    这里只做"清洗"(让文本可读),不做任何分析处理。
    像 $平安银行(SZ000001)$ 这类股票标记、[买入] 表情占位符暂时保留原样,
    是否清洗留到后续分析阶段按需要决定。
    """
    text = re.sub(r"<[^>]+>", "", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_body(session, code, post_id):
    """请求详情页,抽出正文纯文本。

    正文在详情页里是 JSON 字段 "post_content":"<...转义的HTML...>",
    优先解析它;拿不到再退回按 id=newscontent / class=newstext 的容器抽取。
    """
    url = f"{BASE}/news,{code},{post_id}.html"
    r = polite_get(session, url, referer=BASE + "/")
    # 方式1:JSON 字段 post_content(最稳)
    m = re.search(r'"post_content"\s*:\s*"((?:[^"\\]|\\.)*)"', r.text)
    if m:
        try:
            raw = json.loads('"' + m.group(1) + '"')  # 反转义
            return _clean_html(raw)
        except json.JSONDecodeError:
            pass
    # 方式2:HTML 容器兜底
    m = (re.search(r'id="newscontent"[^>]*>(.*?)</div>', r.text, re.S)
         or re.search(r'class="newstext[^"]*"[^>]*>(.*?)</div>', r.text, re.S))
    return _clean_html(m.group(1)) if m else ""


def crawl(code, pages=3, with_body=False):
    session = make_session()
    all_rows = []
    for pg in range(1, pages + 1):
        page_seg = "" if pg == 1 else f"_{pg}"
        url = LIST_URL.format(code=code, page=page_seg)
        r = polite_get(session, url, referer=BASE + "/")
        if r.status_code != 200:
            print(f"[warn] 第 {pg} 页 HTTP {r.status_code},跳过")
            continue
        rows = parse_page(r.text, code)
        print(f"[第 {pg} 页] 解析到 {len(rows)} 条帖子")
        if with_body:
            for row in rows:
                row["content"] = fetch_body(session, code, row["post_id"])
        all_rows.extend(rows)
    return all_rows


def main():
    ap = argparse.ArgumentParser(description="东方财富股吧采集原型")
    ap.add_argument("--code", default="000001", help="股票代码,如 000001 / 600519")
    ap.add_argument("--pages", type=int, default=3, help="抓取页数")
    ap.add_argument("--with-body", action="store_true", help="是否额外抓正文(慢)")
    ap.add_argument("--out", default=None, help="输出 CSV 路径")
    a = ap.parse_args()

    rows = crawl(a.code, a.pages, a.with_body)
    out = a.out or f"data/samples/guba_{a.code}_sample.csv"
    save_csv(rows, out)
    print(f"已保存 {len(rows)} 条 -> {out}")


if __name__ == "__main__":
    main()
