"""雪球"抓包"诊断 —— 开着真实浏览器,你手动登录+手动滚动,脚本把页面真正发出的
带帖子的请求(URL + 条数 + 最旧日期)实时打印。用来定位:雪球加载更早讨论时,
到底调哪个接口、带什么翻页游标。据此改主爬虫,不靠猜。

为什么这么做:
  - 未登录时 stock_timeline 返回 0 条(实测),怀疑要登录。
  - 页面自己能加载帖子,说明它用的接口/参数是对的 —— 直接抓它。

跑法(xueqiu_scraper 目录、venv 激活;必须有头,才能手动登录):
    python probe_capture.py --code 300301

步骤:
  1. 浏览器弹出雪球个股页后,先点右上角登录(扫码/账号都行);
  2. 登录后回到"讨论"列表,用鼠标滚轮**一直往下滚**,滚出越早的帖越好;
  3. 终端会实时打印每个抓到的帖子请求;滚够了回到终端按回车结束。
  4. 把终端打印的"URL 汇总"整段发我。
"""
import argparse
import time


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def prefix(code):
    code = str(code)
    return ("SH" if code[0] in "56" else "SZ") + code


def find_posts(obj):
    """在任意 JSON 里找"像帖子列表"的数组(元素含 id + created_at/text)。"""
    found = []

    def walk(o):
        if isinstance(o, list):
            if o and isinstance(o[0], dict) and o[0].get("id") and \
               ("created_at" in o[0] or "text" in o[0] or "description" in o[0]):
                found.append(o)
            else:
                for x in o:
                    walk(x)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
    walk(obj)
    return found


def oldest_date(lst):
    ds = []
    for it in lst:
        ts = it.get("created_at")
        if isinstance(ts, (int, float)):
            ds.append(time.strftime("%Y-%m-%d", time.localtime(ts / 1000)))
    return min(ds) if ds else "--"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="300301")
    a = ap.parse_args()
    symbol = prefix(a.code)

    seen = {}   # 接口路径 -> {count_calls, max_posts, oldest, sample_url}

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=False,
                              args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        ctx = b.new_context(user_agent=UA, viewport={"width": 1280, "height": 900},
                            ignore_https_errors=True)
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()

        def on_response(resp):
            u = resp.url
            if not any(d in u for d in ("xueqiu.com", "imedao.com")):
                return
            ct = resp.headers.get("content-type", "")
            if "json" not in ct:
                return
            try:
                data = resp.json()
            except Exception:
                return
            for lst in find_posts(data):
                path = u.split("?")[0]
                info = seen.setdefault(path, {"calls": 0, "max_posts": 0,
                                              "oldest": "9999-99-99", "sample_url": u})
                info["calls"] += 1
                info["max_posts"] = max(info["max_posts"], len(lst))
                od = oldest_date(lst)
                if od != "--" and od < info["oldest"]:
                    info["oldest"] = od
                    info["sample_url"] = u   # 记住"翻到更早"的那次的完整 URL(含游标参数)
                print(f"[捕获] {len(lst):>3}条 本次最旧{od}  ->  {u[:130]}", flush=True)

        page.on("response", on_response)

        print(f"打开 https://xueqiu.com/S/{symbol} ...请在浏览器里【登录】,再往下【滚动】加载讨论。")
        page.goto(f"https://xueqiu.com/S/{symbol}", timeout=60000)

        try:
            input("\n>>> 登录并滚动够了后,回到这里按【回车】结束抓包...\n")
        except EOFError:
            page.wait_for_timeout(120000)   # 无法交互时,给 2 分钟手动操作

        b.close()

    print("\n================ 抓到的接口汇总 ================")
    if not seen:
        print("没抓到任何帖子请求。可能:没登录 / 没滚动 / 页面结构变了。")
    for path, info in sorted(seen.items(), key=lambda kv: -kv[1]["max_posts"]):
        print(f"\n接口: {path}")
        print(f"  调用次数 {info['calls']} | 单次最多 {info['max_posts']} 条 | 抓到最旧 {info['oldest']}")
        print(f"  样例完整URL(含翻页参数): {info['sample_url']}")
    print("\n把上面这段【接口汇总】整个发我 —— 我据此把主爬虫改成页面真实用的那个接口+游标。")


if __name__ == "__main__":
    main()
