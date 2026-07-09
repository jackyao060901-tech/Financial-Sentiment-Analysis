"""雪球"登录后能翻多深"决定性测试。

抓包已证实:网页"讨论"列表用的是同域接口
  https://xueqiu.com/query/v1/symbol/search/status.json?...&sort=time&page=N
这正是被卡 ~1000 条(maxPage≈50)的搜索接口。本脚本让你先登录,再用这个【同域】
接口(带登录态、不 CORS)从 page=1 一路翻到 page=80,看登录能不能翻过第 50 页 / 到 2020。

结论只有两种:
  - 翻过 page50 / 日期往 2020 走 → 登录态能突破,主爬虫就走这条(带 cookie)。
  - 卡在 ~page50 / 近端 → 雪球硬顶 1000,2020 不可得,老实交近 1000 条。

跑法(有头,好让你登录):
    python probe_deep.py --code 300301
"""
import argparse
import time

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def prefix(code):
    code = str(code)
    return ("SH" if code[0] in "56" else "SZ") + code


def in_page_get(page, url):
    return page.evaluate(
        "async (u) => { const r = await fetch(u, {headers:{'X-Requested-With':'XMLHttpRequest'}});"
        " const t = await r.text(); try { return {ok:true, status:r.status, json:JSON.parse(t)}; }"
        " catch(e){ return {ok:false, status:r.status, text:t.slice(0,200)}; } }",
        url)


def oldest_of(lst):
    ds = []
    for it in lst:
        ts = it.get("created_at")
        if isinstance(ts, (int, float)):
            ds.append(time.strftime("%Y-%m-%d", time.localtime(ts / 1000)))
    return min(ds) if ds else "--"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="300301")
    ap.add_argument("--pages", type=int, default=80)
    a = ap.parse_args()
    symbol = prefix(a.code)
    # 与网页抓到的完全一致的同域接口
    tmpl = ("https://xueqiu.com/query/v1/symbol/search/status.json"
            "?count=10&comment=0&symbol={sym}&hl=0&source=all&sort=time&page={p}&q=&type=11")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=False,
                              args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        ctx = b.new_context(user_agent=UA, viewport={"width": 1280, "height": 900},
                            ignore_https_errors=True)
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()
        print(f"打开 https://xueqiu.com/S/{symbol} ... 请先在浏览器里【登录雪球】。")
        page.goto(f"https://xueqiu.com/S/{symbol}", timeout=60000)
        try:
            input("\n>>> 登录完成后,回到这里按【回车】开始逐页翻...\n")
        except EOFError:
            page.wait_for_timeout(30000)

        oldest = "9999-99-99"
        max_page_reported = None
        total = 0
        for pg in range(1, a.pages + 1):
            r = in_page_get(page, tmpl.format(sym=symbol, p=pg))
            if not r.get("ok"):
                print(f"  page {pg}: 非JSON status={r.get('status')} {r.get('text','')[:120]}")
                break
            d = r["json"]
            lst = d.get("list") or []
            mp = d.get("maxPage")
            if mp is not None:
                max_page_reported = mp
            od = oldest_of(lst)
            if od != "--" and od < oldest:
                oldest = od
            total += len(lst)
            print(f"  page {pg}: {len(lst)}条 本页最旧{od} 累计最旧{oldest} maxPage={mp}", flush=True)
            if not lst:
                print(f"  -> page {pg} 空,到底/被限。"); break
            time.sleep(1.2)
        b.close()

    print("\n================ 结论 ================")
    print(f"翻到 page 上限:服务器给的 maxPage = {max_page_reported}")
    print(f"累计抓到 {total} 条,最旧日期 {oldest}")
    if oldest <= "2020-12-31":
        print("✅ 登录态翻到了 2020 附近 —— 有戏!主爬虫改成带 cookie 走这个同域接口。")
    elif max_page_reported and max_page_reported <= 60:
        print(f"❌ 服务器硬顶 maxPage={max_page_reported}(约{max_page_reported*10}条),登录也没用。")
        print("   → 雪球 2020 不可得,按老师说的交近 1000 条即可。")
    else:
        print("🟡 结果不明确,把上面每页输出发我一起看。")
    print("把这段结论 + 每页输出发我。")


if __name__ == "__main__":
    main()
