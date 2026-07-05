"""百度贴吧采集原型(走 App 客户端接口 + 公开签名)。

背景与"多渠道"思路:
  贴吧的**网页端**从本云环境(数据中心 IP)访问个股吧列表返回 **403**(反爬/疑封 IP),
  但贴吧的**手机 App 接口** `tiebac.baidu.com/c/f/frs/page` 可用——它需要一个
  **签名 sign**:把参数按 key 排序拼成 `k=v...` 再拼接公开常量 `tiebaclient!!!`,取 MD5 大写。
  这个常量是贴吧 App 的公开协议(非每次会话的私密密钥),相对稳定。

  → 结论:同一平台换个"渠道"(Web → App 接口)就从 403 变成可采。

接口:
  - 帖子列表:POST `c/f/frs/page`,参数 kw(吧名,如"平安银行")、pn 页、rn 每页数。
  - 帖子正文:列表项自带 `abstract` 摘要(默认用它);完整正文可另请求 `c/f/pb/page?kz={tid}`。

注意:
  - 贴吧个股吧噪音较大(广告/招聘/引流帖多),数据质量需在分析阶段清洗。
  - kw 用公司名(如"平安银行"),不是股票代码。

用法:
  python crawlers/baidu_tieba.py --bar 平安银行 --code 000001 --rn 20
"""
import hashlib
import argparse
import datetime

from common import make_session, save_csv, clean_text
import time
import random

APP_UA = "bdtb for Android 12.0"
FRS_URL = "https://tiebac.baidu.com/c/f/frs/page"


def _sign(params):
    """贴吧 App 签名:按 key 排序拼 k=v,尾接 tiebaclient!!!,MD5 大写。"""
    s = "".join(f"{k}={v}" for k, v in sorted(params.items())) + "tiebaclient!!!"
    params["sign"] = hashlib.md5(s.encode("utf-8")).hexdigest().upper()
    return params


def _author_name(author):
    if isinstance(author, dict):
        return author.get("name") or author.get("name_show") or ""
    return ""


def _seg_text(v):
    """贴吧的 abstract/content 常是分段列表 [{text:...}, ...],拼成纯文本。"""
    if isinstance(v, list):
        return "".join(seg.get("text", "") for seg in v if isinstance(seg, dict))
    return v if isinstance(v, str) else ""


def _ts(v):
    try:
        return datetime.datetime.fromtimestamp(int(v)).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, OSError):
        return ""


def crawl(bar, code, rn=20, pages=1):
    session = make_session({"User-Agent": APP_UA})
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for pn in range(1, pages + 1):
        params = _sign({
            "kw": bar, "pn": str(pn), "rn": str(rn),
            "_client_type": "2", "_client_version": "12.0",
        })
        r = session.post(FRS_URL, data=params, timeout=20)
        time.sleep(random.uniform(1.0, 2.5))  # 频率控制
        data = r.json()
        if data.get("error_code") not in (0, "0"):
            print(f"[warn] 第 {pn} 页 error_code={data.get('error_code')} {data.get('error_msg','')}")
            continue
        threads = data.get("thread_list", [])
        print(f"[第 {pn} 页] 解析到 {len(threads)} 条主题帖")
        for th in threads:
            tid = th.get("tid") or th.get("id")
            rows.append({
                "platform": "baidu_tieba",
                "stock_code": code,
                "post_id": tid,
                "title": clean_text(th.get("title", "")),
                "content": clean_text(_seg_text(th.get("abstract"))),  # 列表自带摘要
                "author": _author_name(th.get("author")),
                "author_id": th.get("author_id", ""),
                "publish_time": _ts(th.get("create_time")),
                "read_count": th.get("view_num", ""),
                "comment_count": th.get("reply_num", ""),
                "forward_count": th.get("share_num", ""),
                "bullish_bearish": "",
                "has_pic": "",
                "has_video": "",
                "url": f"https://tieba.baidu.com/p/{tid}",
                "crawl_time": now,
            })
    return rows


def main():
    ap = argparse.ArgumentParser(description="百度贴吧采集原型(App 接口)")
    ap.add_argument("--bar", default="平安银行", help="吧名(公司名),如 平安银行 / 贵州茅台")
    ap.add_argument("--code", default="000001", help="对应股票代码,写入 stock_code")
    ap.add_argument("--rn", type=int, default=20, help="每页条数")
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows = crawl(a.bar, a.code, a.rn, a.pages)
    out = a.out or f"data/samples/tieba_{a.code}_sample.csv"
    save_csv(rows, out)
    print(f"已保存 {len(rows)} 条 -> {out}")


if __name__ == "__main__":
    main()
