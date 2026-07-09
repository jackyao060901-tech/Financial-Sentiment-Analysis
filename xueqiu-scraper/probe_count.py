"""雪球"能不能靠加大 count 突破 1000"决定性测试(登录后跑)。

已知:登录后 search/status 接口 maxPage=100(未登录 50)。若 maxPage 固定=100 而 count
可加大,则 100×count 条 → count=50 就是 5000 条,能冲 2020。本脚本登录后:
  1) 用不同 count(10/30/50/100)各取 page=1,读回 maxPage 和实际返回条数;
     -> 若 count×maxPage 明显 >1000,说明能突破;若始终 ≈1000/2000,说明硬顶。
  2) 直接跳到"最后一页"(page=maxPage)取最旧日期,看极限能到哪年。

跑法(有头,先登录;跑的时候别动浏览器窗口):
    python probe_count.py --code 300301
"""
import argparse
import time

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def prefix(code):
    code = str(code)
    return ("SH" if code[0] in "56" else "SZ") + code


def in_page_get(page, url):
    try:
        return page.evaluate(
            "async (u) => { const r = await fetch(u, {headers:{'X-Requested-With':'XMLHttpRequest'}});"
            " const t = await r.text(); try { return {ok:true, status:r.status, json:JSON.parse(t)}; }"
            " catch(e){ return {ok:false, status:r.status, text:t.slice(0,200)}; } }",
            url)
    except Exception as e:
        return {"ok": False, "text": f"(evaluate失败,浏览器可能被关) {e}"}


def oldest_of(lst):
    ds = []
    for it in lst:
        ts = it.get("created_at")
        if isinstance(ts, (int, float)):
            ds.append(time.strftime("%Y-%m-%d", time.localtime(ts / 1000)))
    return min(ds) if ds else "--"


def url_for(sym, count, page):
    return (f"https://xueqiu.com/query/v1/symbol/search/status.json"
            f"?count={count}&comment=0&symbol={sym}&hl=0&source=all&sort=time&page={page}&q=&type=11")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="300301")
    a = ap.parse_args()
    sym = prefix(a.code)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=False,
                              args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        ctx = b.new_context(user_agent=UA, viewport={"width": 1280, "height": 900},
                            ignore_https_errors=True)
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()
        print(f"打开 https://xueqiu.com/S/{sym} ... 请先【登录雪球】。")
        page.goto(f"https://xueqiu.com/S/{sym}", timeout=60000)
        try:
            input("\n>>> 登录完成后按【回车】开始(之后别碰浏览器窗口)...\n")
        except EOFError:
            page.wait_for_timeout(30000)

        print("\n--- 测试1:不同 count 下的 maxPage(看总量上限) ---")
        best = {"count": 10, "maxPage": 100}
        for c in (10, 30, 50, 100):
            r = in_page_get(page, url_for(sym, c, 1))
            if not r.get("ok"):
                print(f"  count={c}: 失败 {r.get('text','')[:100]}"); continue
            d = r["json"]; lst = d.get("list") or []; mp = d.get("maxPage")
            cap = (mp or 0) * len(lst)
            print(f"  count={c}: 实际返回{len(lst)}条/页, maxPage={mp}  => 理论总量≈{mp}×{len(lst)}={cap}")
            if cap > best["maxPage"] * (10 if best["count"] == 10 else best["count"]):
                best = {"count": len(lst), "maxPage": mp or 0}
            time.sleep(1.0)

        print("\n--- 测试2:跳到最后一页看极限日期 ---")
        for c in (10, 50):
            r = in_page_get(page, url_for(sym, c, 1))
            if not r.get("ok"):
                continue
            mp = (r["json"].get("maxPage")) or 100
            r2 = in_page_get(page, url_for(sym, c, mp))
            if r2.get("ok"):
                lst = r2["json"].get("list") or []
                print(f"  count={c} 的最后一页 page={mp}: {len(lst)}条 最旧{oldest_of(lst)}")
            time.sleep(1.0)
        b.close()

    print("\n================ 怎么读 ================")
    print("若某个 count 的『理论总量』明显 >2000(比如 count=50→5000)→ 能突破,冲 2020!")
    print("若不管 count 多大,总量都卡在 ~1000/2000、最后一页仍停在近端 → 雪球硬顶,交近千条。")
    print("把上面【测试1 + 测试2】全部输出发我。")


if __name__ == "__main__":
    main()
