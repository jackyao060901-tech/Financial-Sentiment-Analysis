"""
微信公众号文章批量下载器。

先获取 URL 列表（随便哪种方式），然后批量下载。

用法:
  python wechat_downloader.py urls.txt              # 从文件读取 URL 列表
  python wechat_downloader.py --url "https://mp..."  # 下载单篇
"""

import sys, re, time, requests
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path("wechat_articles")


def download_article(url: str) -> dict | None:
    """下载单篇公众号文章，返回 {title, date, content, url}"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; MI 9) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/88.0.4324.181 Mobile Safari/537.36 "
                      "MicroMessenger/8.0.0.1840",
    }

    try:
        r = requests.get(url.strip(), headers=headers, timeout=15)
        r.raise_for_status()
    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        return None

    html = r.text

    # Extract title
    title_m = re.search(r'var msg_title\s*=\s*[\'"](.+?)[\'"]', html)
    title = title_m.group(1) if title_m else "unknown"

    # Extract date
    date_m = re.search(r'var ct\s*=\s*[\'"](\d+)[\'"]', html)
    date_str = ""
    if date_m:
        try:
            date_str = datetime.fromtimestamp(int(date_m.group(1))).strftime("%Y-%m-%d")
        except:
            pass

    # Extract content (js_content div)
    content_m = re.search(r'id="js_content"[^>]*>(.*?)</div>\s*<script', html, re.DOTALL)
    if not content_m:
        print(f"  ❌ No content found")
        return None

    raw = content_m.group(1)
    # Clean HTML
    text = re.sub(r'<section[^>]*>', '\n', raw)
    text = re.sub(r'</section>', '', text)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    # Save as markdown
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)[:60]
    filename = f"{date_str}_{safe_title}.md" if date_str else f"{safe_title}.md"
    filepath = OUTPUT_DIR / filename

    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# {title}\n\n")
        if date_str:
            f.write(f"*{date_str}*\n\n")
        f.write(f"原文: {url}\n\n---\n\n")
        f.write(text)

    return {
        "title": title,
        "date": date_str,
        "content": text,
        "file": str(filepath),
        "url": url,
        "chars": len(text),
    }


if __name__ == "__main__":
    urls = []

    if len(sys.argv) > 1:
        if sys.argv[1] == "--url" and len(sys.argv) > 2:
            urls = [sys.argv[2]]
        else:
            # Read from file
            with open(sys.argv[1]) as f:
                urls = [l.strip() for l in f if l.strip() and 'mp.weixin.qq.com' in l]
    else:
        print("Usage: python wechat_downloader.py urls.txt")
        print("       python wechat_downloader.py --url 'https://mp.weixin.qq.com/s/...'")
        sys.exit(1)

    print(f"Downloading {len(urls)} articles to {OUTPUT_DIR}/\n")

    ok = 0
    for i, url in enumerate(urls):
        result = download_article(url)
        if result:
            print(f"  [{i+1}/{len(urls)}] ✅ {result['date']} {result['title'][:50]} ({result['chars']} chars)")
            ok += 1
        else:
            print(f"  [{i+1}/{len(urls)}] ❌ {url[:60]}...")
        time.sleep(1)

    print(f"\n✅ {ok}/{len(urls)} downloaded → {OUTPUT_DIR}/")
