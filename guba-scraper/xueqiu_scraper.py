"""
雪球用户文章批量下载器。

Playwright headed mode 绕过阿里云 WAF，直接调 API 获取全部文章。
输出 Markdown 格式。

用法:
  python xueqiu_scraper.py <user_id> [output_dir]
  python xueqiu_scraper.py 1938071719 ~/Desktop/ST-PhD-文章
"""

import sys, re, os
from datetime import datetime
from playwright.sync_api import sync_playwright


def scrape_user(user_id: str, output_dir: str = "xueqiu_articles"):
    os.makedirs(output_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        page.goto(f"https://xueqiu.com/u/{user_id}", timeout=60000)
        page.wait_for_timeout(8000)

        name = re.search(r'screen_name["\']:\s*["\']([^"\']+)', page.content())
        name = name.group(1) if name else user_id
        print(f"抓取 @{name} 全部文章...")

        all_articles = []
        for page_num in range(1, 500):
            result = page.evaluate(f"""
                async () => {{
                    const r = await fetch('/v4/statuses/user_timeline.json?user_id={user_id}&page={page_num}&type=0');
                    return await r.json();
                }}
            """)

            items = result.get("statuses", [])
            if not items:
                break

            for item in items:
                aid = item.get("id")
                title = (item.get("title") or "").strip()
                desc = (item.get("description") or item.get("text") or "").strip()
                desc = re.sub(r'<[^>]+>', '', desc)

                ts = item.get("created_at", 0)
                date_str = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") if ts > 1e9 else str(ts)[:10]

                safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)[:60]
                filepath = os.path.join(output_dir, f"{date_str}_{safe_title}.md")

                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"# {title}\n\n")
                    f.write(f"*雪球 @{name} | {date_str} | ♻{item.get('retweet_count',0)} 💬{item.get('reply_count',0)}*\n\n")
                    f.write(f"原文: https://xueqiu.com/{aid}\n\n---\n\n")
                    f.write(desc)

                all_articles.append({"id": aid, "title": title, "date": date_str})

            print(f"  Page {page_num}: {len(items)} articles (累计 {len(all_articles)})")
            if len(items) < 20:
                break
            page.wait_for_timeout(600)

        browser.close()
        print(f"\n✅ {len(all_articles)} 篇 → {output_dir}")
        return all_articles


if __name__ == "__main__":
    uid = sys.argv[1] if len(sys.argv) > 1 else "1938071719"
    out = sys.argv[2] if len(sys.argv) > 2 else "xueqiu_articles"
    scrape_user(uid, out)
