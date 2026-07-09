"""雪球接口翻页诊断 —— 在能连雪球的本地/住宅 IP 上跑,测出哪种翻页能往更早走。

背景:主爬虫 stock_timeline 用 max_id 翻页,实测卡在第一批(10条不动)。
怀疑该接口只认 page=N。这个脚本用你的真实浏览器(已能过 WAF)逐一实测下面几种翻法,
把"每种能翻到多旧、翻了多少页、每页多少条"打出来,据此决定主爬虫怎么改。

跑法(在 xueqiu_scraper 目录、venv 激活状态):
    python probe_endpoints.py                 # 默认 300301,有头
    python probe_endpoints.py --code 300301 --headless
"""
import argparse
import json
import time

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def prefix(code):
    code = str(code)
    return ("SH" if code[0] in "56" else "SZ") + code


def in_page_get(page, url):
    """在页面里 fetch,带完整会话态(cookie/token),返回解析后的 JSON。"""
    return page.evaluate(
        "async (u) => { const r = await fetch(u, {headers:{'X-Requested-With':'XMLHttpRequest'}});"
        " const t = await r.text(); try { return {ok:true, status:r.status, json:JSON.parse(t)}; }"
        " catch(e){ return {ok:false, status:r.status, text:t.slice(0,300)}; } }",
        url)


def dates_of(lst):
    """从帖子列表里取时间(created_at 毫秒时间戳 -> 日期字符串)。"""
    out = []
    for it in lst:
        if not isinstance(it, dict):
            continue
        ts = it.get("created_at")
        if isinstance(ts, (int, float)):
            out.append(time.strftime("%Y-%m-%d", time.localtime(ts / 1000)))
    return out


def walk(page, label, url_tmpl, symbol, page_key, max_pages=40):
    """按 page_key(page 或 max_id)翻 max_pages 页,报告能翻到多旧、每页条数、何时到底。"""
    print(f"\n===== 试 [{label}] =====")
    seen_ids = set()
    oldest = "9999-99-99"
    cursor = None            # max_id 模式用
    empties = 0
    for p in range(1, max_pages + 1):
        if page_key == "page":
            url = url_tmpl.format(symbol=symbol, page=p)
        else:  # max_id 模式
            url = url_tmpl.format(symbol=symbol) + (f"&max_id={cursor}" if cursor else "")
        r = in_page_get(page, url)
        if not r.get("ok"):
            print(f"  第{p}页: 非JSON status={r.get('status')} {r.get('text','')[:120]}")
            break
        d = r["json"]
        lst = d.get("list") or d.get("statuses") or (d.get("data") or {}).get("list") or []
        new_ids = [it.get("id") for it in lst if isinstance(it, dict) and it.get("id") not in seen_ids]
        ds = dates_of(lst)
        if ds:
            oldest = min(oldest, min(ds))
        for it in lst:
            if isinstance(it, dict) and it.get("id"):
                seen_ids.add(it.get("id"))
        if lst:
            cursor = lst[-1].get("id") or cursor
        print(f"  第{p}页: 返回{len(lst)}条 新{len(new_ids)}条 本页最旧{min(ds) if ds else '--'} "
              f"累计最旧{oldest} 累计去重{len(seen_ids)}")
        if not lst or not new_ids:
            empties += 1
            if empties >= 2:
                print(f"  -> 连续无新增,判定到底/被限。累计去重 {len(seen_ids)} 条,最旧 {oldest}")
                break
        else:
            empties = 0
        time.sleep(1.5)
    print(f"  [{label}] 结论:翻了≤{max_pages}页,去重 {len(seen_ids)} 条,最旧 {oldest}")
    return oldest, len(seen_ids)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="300301")
    ap.add_argument("--headless", action="store_true")
    a = ap.parse_args()
    symbol = prefix(a.code)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=a.headless,
                              args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        ctx = b.new_context(user_agent=UA, viewport={"width": 1280, "height": 800},
                            ignore_https_errors=True)
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()
        print(f"打开 https://xueqiu.com/S/{symbol} 过 WAF ...")
        page.goto(f"https://xueqiu.com/S/{symbol}", timeout=60000)
        page.wait_for_timeout(8000)

        # 先看一眼原始返回结构(第1页),确认字段名
        raw = in_page_get(page, f"/statuses/stock_timeline.json?symbol_id={symbol}&count=20&source=&page=1")
        print("\n[原始结构预览] status=", raw.get("status"), " ok=", raw.get("ok"))
        if raw.get("ok"):
            d = raw["json"]
            print("  顶层键:", list(d.keys())[:12])
            lst = d.get("list") or []
            print("  list 长度:", len(lst))
            if lst:
                print("  单条键:", list(lst[0].keys())[:20])
        else:
            print("  非JSON:", raw.get("text", "")[:200])

        # A: stock_timeline 用 page 翻页(source 留空)
        walk(page, "stock_timeline?page (source=)",
             "https://xueqiu.com/statuses/stock_timeline.json?symbol_id={symbol}&count=20&source=&page={page}",
             symbol, "page")

        # B: stock_timeline 用 page 翻页(source=all)
        walk(page, "stock_timeline?page (source=all)",
             "https://xueqiu.com/statuses/stock_timeline.json?symbol_id={symbol}&count=20&source=all&page={page}",
             symbol, "page")

        # C: 搜索接口用 page(已知 ~1000 上限,做对照)
        walk(page, "search/status?page (对照)",
             "https://api.xueqiu.com/query/v1/symbol/search/status.json?symbol={symbol}&count=20&source=all&sort=time&page={page}",
             symbol, "page")

        # D: stock_timeline 用 max_id(当前主爬虫用的,复现"卡住")
        walk(page, "stock_timeline max_id (当前爬虫做法)",
             "https://xueqiu.com/statuses/stock_timeline.json?symbol_id={symbol}&count=20&source=all",
             symbol, "max_id")

        b.close()
    print("\n把上面 A/B/C/D 四段结果全发我 —— 哪段'累计去重'最多、'最旧'最早,主爬虫就改用哪种。")


if __name__ == "__main__":
    main()
