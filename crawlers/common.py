"""各平台爬虫共用工具:统一的会话、礼貌请求(带频率控制)、统一字段的 CSV 落盘。

字段(FIELDS)在所有平台间保持一致,是为了以后做情绪分析时能直接拼在一起用。
即使某平台拿不到某个字段,也保留列、留空,不要改结构。
"""
import os
import re
import csv
import html
import time
import random
import requests

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 统一的帖子字段。所有平台的采集结果都映射到这套字段。
FIELDS = [
    "platform",        # 来源平台,如 eastmoney_guba / xueqiu
    "stock_code",      # 股票代码
    "post_id",         # 帖子唯一 id
    "title",           # 标题
    "content",         # 正文(可能为空,需额外请求详情页)
    "author",          # 作者昵称
    "author_id",       # 作者 id
    "publish_time",    # 发帖时间
    "read_count",      # 阅读数
    "comment_count",   # 评论数
    "forward_count",   # 转发数
    "bullish_bearish", # 平台自带的看涨/看跌标记(如有),以后可当情绪的参照
    "has_pic",         # 是否含图
    "has_video",       # 是否含视频
    "url",             # 帖子链接
    "crawl_time",      # 采集时间
]


def make_session(extra_headers=None):
    """创建一个带默认浏览器头的 requests 会话。"""
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    if extra_headers:
        s.headers.update(extra_headers)
    return s


def polite_get(session, url, referer=None, timeout=20,
               min_delay=1.0, max_delay=2.5, retries=3, **kwargs):
    """发一次 GET,失败自动重试,并在之后随机 sleep 做频率控制。

    - 频率控制:既是对目标站的礼貌,也能降低被反爬封 IP 的概率。
    - 重试:网络/代理偶发抖动(如 DNS 瞬时失败)时,指数退避重试,避免整轮采集崩溃。
    """
    if referer:
        headers = kwargs.setdefault("headers", {})
        headers.setdefault("Referer", referer)
    last_err = None
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=timeout, **kwargs)
            time.sleep(random.uniform(min_delay, max_delay))
            return resp
        except requests.RequestException as e:
            last_err = e
            wait = 2 ** attempt  # 1s, 2s, 4s
            print(f"[retry] 请求失败({type(e).__name__}),{wait}s 后重试:{url[:60]}")
            time.sleep(wait)
    raise last_err


def clean_text(raw):
    """通用文本清洗:去 HTML 标签、解码实体(&nbsp; &gt; 等)、压缩空白。

    只做"清洗"(让文本干净可读),不做分词/情感等分析处理。
    """
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", "", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def save_csv(rows, path):
    """把统一字段的行写成 CSV。用 utf-8-sig 让 Excel 正确显示中文。"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in FIELDS})
    return path
