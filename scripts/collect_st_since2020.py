"""专项批量采集:5 只 ST 股的东方财富股吧帖子,尽量回溯到 2020 年。

背景:老师指定的 5 只 ST(退市风险)股,情绪博弈浓,适合舆情分析。
策略(单 IP 现实约束下):
  - 只抓**列表级**(标题/时间/阅读/评论/作者),不抓正文——几千页抓正文单 IP 必被秒封。
    股吧散户帖很多本就只有标题,列表级已是学界常用的股吧情绪数据。
  - 每只股票从第 1 页(最新)向后翻,直到:最旧帖 < 2020-01-01 / 连续失败(疑限流)/ 到页数上限。
  - **边爬边存、按 post_id 去重**;被封也保留已采部分,并记录停在哪。

产出:
  - data/st_since2020/{code}_{name}.csv   每只一个
  - 采集过程打印每只的覆盖情况(页数、日期范围、停止原因),供写报告。
"""
import sys
import os
import time
import random
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "crawlers"))
import eastmoney_guba as g          # noqa: E402
from common import make_session, save_csv  # noqa: E402

BASE = "https://guba.eastmoney.com"
STOCKS = [
    ("300301", "ST长方"),
    ("002816", "ST和科"),
    ("688646", "ST逸飞"),
    ("688076", "ST诺泰"),
    ("002055", "ST得润"),
]
SINCE = "2020-01-01"
MAX_PAGES = 900          # 安全上限
MAX_FAILS = 5           # 连续失败判为限流/封禁


def crawl_stock(session, code, name):
    seen = set()
    rows = []
    fails = 0
    stop_reason = f"达到页数上限 {MAX_PAGES} 页(未及 2020,可提高上限或换 IP 续采)"
    last_page = 0
    for pg in range(1, MAX_PAGES + 1):
        seg = "" if pg == 1 else f"_{pg}"
        url = f"{BASE}/list,{code}{seg}.html"
        try:
            r = session.get(url, headers={"Referer": BASE + "/"}, timeout=20)
        except Exception as e:
            fails += 1
            print(f"    [{code}] 第{pg}页 请求异常({type(e).__name__}) 连续失败{fails}")
            if fails >= MAX_FAILS:
                stop_reason = f"连续{fails}次请求异常(疑网络/限流),停在第{pg}页"
                break
            time.sleep(3 * fails)
            continue
        if r.status_code != 200:
            fails += 1
            print(f"    [{code}] 第{pg}页 HTTP {r.status_code} 连续失败{fails}")
            if fails >= MAX_FAILS:
                stop_reason = f"连续{fails}次 HTTP {r.status_code}(疑限流/封IP),停在第{pg}页"
                break
            time.sleep(3 * fails)
            continue
        page_rows = g.parse_page(r.text, code)
        if not page_rows:
            fails += 1
            if fails >= MAX_FAILS:
                stop_reason = f"连续{fails}次解析为空(疑到底/被拦),停在第{pg}页"
                break
            time.sleep(2 * fails)
            continue
        fails = 0
        last_page = pg
        new = 0
        for x in page_rows:
            pid = x["post_id"]
            if pid in seen:
                continue
            seen.add(pid)
            rows.append(x)
            new += 1
        times = [x["publish_time"] for x in page_rows if x["publish_time"]]
        oldest = min(times) if times else ""
        if pg % 25 == 0 or pg <= 3:
            print(f"    [{code}] 第{pg}页 +{new} 累计{len(rows)} 最旧 {oldest[:10]}")
        if oldest and oldest < SINCE:
            stop_reason = f"已回溯到 {SINCE} 之前(第{pg}页),完成"
            break
        time.sleep(random.uniform(1.0, 1.8))   # 频率控制
    # 只保留 >= 2020 的
    rows = [x for x in rows if x["publish_time"] >= SINCE]
    rows.sort(key=lambda x: x["publish_time"])
    return rows, last_page, stop_reason


def main():
    session = make_session()
    summary = []
    for code, name in STOCKS:
        print(f"== 采集 {name}({code}) ==")
        rows, last_page, reason = crawl_stock(session, code, name)
        out = f"data/st_since2020/{code}_{name}.csv"
        save_csv(rows, out)
        if rows:
            dmin = rows[0]["publish_time"][:10]
            dmax = rows[-1]["publish_time"][:10]
        else:
            dmin = dmax = "-"
        print(f"  -> {name}: {len(rows)} 条, {dmin}~{dmax}, 翻到第{last_page}页, {reason}\n")
        summary.append((code, name, len(rows), dmin, dmax, last_page, reason))
    print("=== 汇总 ===")
    for code, name, n, dmin, dmax, lp, reason in summary:
        print(f"  {name}({code}): {n}条 {dmin}~{dmax} 第{lp}页 | {reason}")


if __name__ == "__main__":
    main()
