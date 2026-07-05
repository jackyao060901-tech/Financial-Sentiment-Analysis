"""统一采样驱动:对所有已跑通的平台,用同一组股票批量采集样本。

- 便于复现:一条命令重建 data/samples/ 下全部样本。
- 股票池覆盖不同行业与大小盘,让样本更有代表性。

用法:
  python scripts/collect_samples.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "crawlers"))

from common import save_csv  # noqa: E402
import eastmoney_guba, sina_finance, ths_news, taoguba, eastmoney_news  # noqa: E402

# 股票池:银行 / 白酒 / 新能源(创业板)/ 安防 / 保险(沪大盘)
STOCKS = [
    ("000001", "sz000001", "平安银行"),
    ("600519", "sh600519", "贵州茅台"),
    ("300750", "sz300750", "宁德时代"),
    ("002415", "sz002415", "海康威视"),
    ("601318", "sh601318", "中国平安"),
]

PER_STOCK = 10  # 每只股票每平台目标条数


def collect_eastmoney_guba():
    rows = []
    s = eastmoney_guba.make_session()
    for code, _, name in STOCKS:
        r = eastmoney_guba.crawl(code, pages=1)[:PER_STOCK]
        for x in r:
            x["content"] = eastmoney_guba.fetch_body(s, code, x["post_id"])
        print(f"  东财股吧 {code} {name}: {len(r)}")
        rows += r
    save_csv(rows, "data/samples/guba_sample.csv")
    return len(rows)


def collect_sina():
    rows = []
    s = sina_finance.make_session()
    for _, sym, name in STOCKS:
        r = sina_finance.crawl(sym, pages=1)[:PER_STOCK]
        for x in r:
            x["content"] = sina_finance.fetch_body(s, x["url"])
        print(f"  新浪股吧 {sym} {name}: {len(r)}")
        rows += r
    save_csv(rows, "data/samples/sina_sample.csv")
    return len(rows)


def collect_ths():
    rows = []
    for code, _, name in STOCKS:
        r = ths_news.crawl(code, pages=1)[:PER_STOCK]
        print(f"  同花顺资讯 {code} {name}: {len(r)}")
        rows += r
    save_csv(rows, "data/samples/ths_news_sample.csv")
    return len(rows)


def collect_taoguba():
    rows = []
    for _, sym, name in STOCKS:
        r = taoguba.crawl(sym, limit=PER_STOCK)
        print(f"  淘股吧 {sym} {name}: {len(r)}")
        rows += r
    save_csv(rows, "data/samples/taoguba_sample.csv")
    return len(rows)


def collect_eastmoney_news():
    rows = []
    for code, _, name in STOCKS:
        r = eastmoney_news.crawl(code, count=PER_STOCK, with_body=True)
        print(f"  东财新闻 {code} {name}: {len(r)}")
        rows += r
    save_csv(rows, "data/samples/eastmoney_news_sample.csv")
    return len(rows)


def main():
    totals = {}
    for name, fn in [
        ("东财股吧", collect_eastmoney_guba),
        ("新浪股吧", collect_sina),
        ("同花顺资讯", collect_ths),
        ("淘股吧", collect_taoguba),
        ("东财新闻", collect_eastmoney_news),
    ]:
        print(f"== 采集 {name} ==")
        try:
            totals[name] = fn()
        except Exception as e:
            print(f"  [error] {name} 失败: {type(e).__name__}: {e}")
            totals[name] = 0
    print("\n=== 汇总 ===")
    for k, v in totals.items():
        print(f"  {k}: {v} 条")
    print(f"  合计: {sum(totals.values())} 条")


if __name__ == "__main__":
    main()
