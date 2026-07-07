"""
ST 股票股吧全量批量抓取脚本。

用法:
  python batch_scrape.py                    # 抓取所有 ST 股 (全量历史)
  python batch_scrape.py --daily            # 每日增量 (只抓前2页)
  python batch_scrape.py --resume           # 断点续传
  python batch_scrape.py --stock 002141     # 只抓单只

设计:
  - 1.5s 页间隔, 5s 股间隔 → 不会被封
  - 断点续传 → 意外中断后从上次位置继续
  - 进度保存到 progress.json
  - 数据存 SQLite (st_guba.db)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from scraper import GubaScraper

PROGRESS_FILE = "progress.json"
DB_FILE = "st_guba.db"


def get_st_list() -> list[tuple[str, str]]:
    """获取当前 ST 股票列表 (多源 fallback)。"""
    # 方法1: BaoStock
    try:
        import baostock as bs
        bs.login()
        rs = bs.query_stock_basic(code_name="ST")
        data = rs.get_data()
        bs.logout()
        # 只取当前上市的 ST (status=1)
        active = data[data["status"] == "1"]
        codes = []
        for _, row in active.iterrows():
            c = row["code"].replace("sh.", "").replace("sz.", "")
            codes.append((c, row["code_name"]))
        if codes:
            return codes
    except Exception:
        pass

    # 方法2: 硬编码常用 ST 列表 (兜底)
    return [
        ("002141", "贤丰控股"),
        ("600079", "ST人福"),
        ("600053", "*ST九鼎"),
        # ... 需要补全
    ]


def load_progress() -> dict:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"completed": {}, "current_stock": None, "current_page": 1}


def save_progress(progress: dict):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2, default=str)


def main():
    ap = argparse.ArgumentParser(description="ST 股吧批量抓取")
    ap.add_argument("--daily", action="store_true", help="每日增量模式 (每只2页)")
    ap.add_argument("--resume", action="store_true", help="从上次中断处继续")
    ap.add_argument("--stock", help="只抓取指定股票代码")
    ap.add_argument("--max-pages", type=int, default=0, help="每只最大页数 (0=全量)")
    ap.add_argument("--start-page", type=int, default=1, help="起始页")
    args = ap.parse_args()

    # 获取 ST 列表
    if args.stock:
        stocks = [(args.stock, args.stock)]
    else:
        stocks = get_st_list()

    print(f"共 {len(stocks)} 只 ST 股票")
    if args.daily:
        print("模式: 每日增量 (每只前2页)")
    else:
        print("模式: 全量历史 (直到无数据)")

    # 加载进度
    progress = {} if not args.resume else load_progress()
    scraper = GubaScraper(db_path=DB_FILE, delay=1.5)

    # 遍历股票
    for i, (code, name) in enumerate(stocks):
        # 断点续传: 跳过已完成的
        if code in progress.get("completed", {}):
            pages_done = progress["completed"][code]
            print(f"[{i+1}/{len(stocks)}] {code} {name} — 已完成 {pages_done} 页, 跳过")
            continue

        # 计算要抓取的页数
        if args.daily:
            max_pages = 2
        elif args.max_pages > 0:
            max_pages = args.max_pages
        else:
            # 自动检测总页数
            try:
                r = requests.get(
                    f"https://guba.eastmoney.com/list,{code}.html",
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=15,
                )
                import re
                total_m = re.search(r'"count"\s*:\s*(\d+)', r.text)
                total = int(total_m.group(1)) if total_m else 0
                max_pages = total // 80 + 1
            except Exception:
                max_pages = 100  # fallback

        start_page = progress.get("current_page", args.start_page) if code == progress.get("current_stock") else 1

        print(f"\n[{i+1}/{len(stocks)}] {code} {name} — {max_pages} 页")
        t0 = time.time()

        # 分批抓取 (每50页保存一次进度)
        for batch_start in range(start_page, max_pages + 1, 50):
            batch_end = min(batch_start + 49, max_pages)
            posts = scraper.fetch_stock_posts(code, pages=batch_end - batch_start + 1, start_page=batch_start)

            progress["current_stock"] = code
            progress["current_page"] = batch_end + 1
            save_progress(progress)

            elapsed = time.time() - t0
            total_posts = sum(progress["completed"].values()) + len(posts)
            print(f"  {batch_start}-{batch_end}: {len(posts)} posts | 累计: {elapsed:.0f}s | 已入库: {total_posts:,}")

            # 如果连续3批都没数据，说明到底了
            if len(posts) < 10 and batch_start > 1:
                print(f"  数据稀疏，可能到底了，结束 {code}")
                break

        # 标记完成
        progress.setdefault("completed", {})[code] = max_pages
        progress["current_stock"] = None
        progress["current_page"] = 1
        save_progress(progress)

        print(f"  ✅ {code} 完成 ({max_pages} 页, {time.time()-t0:.0f}s)")
        time.sleep(5)  # 换股票前的间隔

    print(f"\n全部完成! 数据库: {DB_FILE}")


if __name__ == "__main__":
    main()
