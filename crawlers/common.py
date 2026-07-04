"""各平台爬虫共用工具:统一的会话、礼貌请求(带频率控制)、统一字段的 CSV 落盘。

字段(FIELDS)在所有平台间保持一致,是为了以后做情绪分析时能直接拼在一起用。
即使某平台拿不到某个字段,也保留列、留空,不要改结构。
"""
import os
import csv
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
               min_delay=1.0, max_delay=2.5, **kwargs):
    """发一次 GET,并在之后随机 sleep 一小段时间做频率控制。

    频率控制很重要:既是对目标站的礼貌,也能降低被反爬封 IP 的概率。
    """
    if referer:
        headers = kwargs.setdefault("headers", {})
        headers.setdefault("Referer", referer)
    resp = session.get(url, timeout=timeout, **kwargs)
    time.sleep(random.uniform(min_delay, max_delay))
    return resp


def save_csv(rows, path):
    """把统一字段的行写成 CSV。用 utf-8-sig 让 Excel 正确显示中文。"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in FIELDS})
    return path
