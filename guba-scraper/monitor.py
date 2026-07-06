"""ST 股吧爬虫监控面板。python3 monitor.py → http://localhost:8899"""
from __future__ import annotations
import json, subprocess, sys, time, sqlite3, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from urllib.parse import urlparse, parse_qs

WATCHLIST = {
    "300301": "ST长方/电子",
    "002211": "ST宏达/化工",
    "002816": "*ST和科/机械设备",
    "300020": "ST银江/计算机",
    "002102": "ST能特/医药生物",
}

SSH_HOST = "yizhang@202.120.22.16"
SSH_PORT = "10022"
REMOTE_DIR = "gf-sector-scan/guba-scraper"
get_db_path() = os.path.join(os.path.dirname(os.path.abspath(__file__)), "st_guba.db")
SERVER_DB = os.path.expanduser("~/Desktop/gf-sector-scan/guba-scraper/st_guba.db")
_sync_ts = 0

def get_db_path():
    """Use local DB (multi-threaded scraper writes here)."""
    if os.path.exists(SERVER_DB):
        return SERVER_DB
    return get_db_path()

def sync():
    return True  # Local DB — no sync needed

def q(sql, params=()):
    sync()
    if not os.path.exists(get_db_path()): return []
    db = sqlite3.connect(get_db_path())
    return db.execute(sql, params).fetchall()

def q1(sql, params=()):
    rows = q(sql, params)
    return rows[0] if rows else None

def render_page(path):
    parsed = urlparse(path)
    params = parse_qs(parsed.query)
    month = params.get("month", [None])[0]
    page_num = int(params.get("page", [1])[0])
    limit = 30
    offset = (page_num - 1) * limit

    # ── Overall stats ──
    r = q1("SELECT COUNT(*),COUNT(DISTINCT stock_code),MIN(publish_time),MAX(publish_time) FROM posts")
    total_posts, total_stocks_db, earliest, latest = (r[0],r[1],str(r[2])[:10],str(r[3])[:10]) if r else (0,0,"?","?")

    # Current stock detail
    cur = q1("SELECT stock_code,stock_name,COUNT(*) FROM posts GROUP BY 1 ORDER BY 3 DESC LIMIT 1")
    cur_code, cur_name, cur_posts = cur if cur else ("?","?",0)
    cur_pages_done = cur_posts // 80

    # Remote progress
    prog = {}
    prog_out = ssh(f"cat {REMOTE_DIR}/progress.json 2>/dev/null")
    if prog_out:
        try: prog = json.loads(prog_out)
        except: pass
    stocks_done = len(prog.get("completed",{}))
    total_stocks = 207
    cur_page = prog.get("current_page","?")
    cur_remote = prog.get("current_stock","?")

    # Per-year breakdown
    yrs = q("SELECT substr(publish_time,1,4) as yr, COUNT(*) FROM posts GROUP BY yr ORDER BY yr")
    year_bars = ""
    for yr, cnt in yrs:
        pct = min(cnt / max(total_posts, 1) * 100, 100)
        year_bars += f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0"><span style="width:50px;text-align:right;font-size:13px;color:#94a3b8">{yr}</span><div style="flex:1;background:#334155;border-radius:4px;height:16px"><div style="background:linear-gradient(90deg,#0ea5e9,#38bdf8);height:100%;border-radius:4px;width:{pct:.1f}%"></div></div><span style="font-size:13px;color:#64748b;width:80px">{cnt:,}条</span></div>'

    # Per-month detail
    months_data = q("SELECT substr(publish_time,1,7) as m, COUNT(*) FROM posts GROUP BY m ORDER BY m DESC")
    month_opts = ""
    for m, _ in months_data:
        label = f"{m[:4]}年{m[5:]}月"
        sel = " selected" if m == month else ""
        month_opts += f'<option value="{m}"{sel}>{label}</option>'

    # ── Watchlist (表哥关注的 5 只 ST) ──
    watch_html = ""
    for wcode, wname in WATCHLIST.items():
        wr = q1("SELECT COUNT(*),MAX(publish_time) FROM posts WHERE stock_code=?", (wcode,))
        wcnt, wlast = wr if wr else (0, "无数据")
        watch_html += f'<div class="stat"><div class="num">{wcnt:,}</div><div class="label">{wcode}<br>{wname}</div><div style="font-size:10px;color:#64748b;margin-top:4px">最新: {str(wlast)[:16] if wlast else "—"}</div></div>'

    # Posts for display
    if month:
        posts_rows = q("SELECT title,author,publish_time,reads,comments,stock_name,stock_code FROM posts WHERE substr(publish_time,1,7)=? ORDER BY publish_time DESC LIMIT ? OFFSET ?", (month, limit, offset))
    else:
        posts_rows = q("SELECT title,author,publish_time,reads,comments,stock_name,stock_code FROM posts ORDER BY publish_time DESC LIMIT ? OFFSET ?", (limit, offset))

    post_html = ""
    for r in posts_rows:
        post_html += f'<div class="post"><div class="title">{r[0]}</div><div class="meta"><span class="stock-tag">📌{r[6]} {r[5]}</span><span>👤{r[1]}</span><span>🕐{r[2]}</span><span>👁{r[3]:,}</span><span>💬{r[4]}</span></div></div>'
    if not post_html:
        post_html = '<div style="text-align:center;color:#64748b;padding:40px">暂无数据</div>'

    # Uptime
    upt = ssh("ps -o etimes= -p $(pgrep -f batch_scrape|head -1) 2>/dev/null")
    elapsed = "—"
    speed_str = ""
    if upt and upt.strip().isdigit():
        secs = int(upt.strip())
        h, m = divmod(secs, 3600); m, s = divmod(m, 60)
        elapsed = f"{h}h{m}m{s}s" if h else f"{m}m{s}s"
        if secs > 0 and total_posts > 0:
            pps = total_posts / secs
            speed_str = f" | {pps:.0f} 帖/秒"

    # Pagination
    prev_btn = f'<a href="/?month={month or ""}&page={page_num-1}" class="btn" {"disabled" if page_num<=1 else ""}>← 上一页</a>'
    next_btn = f'<a href="/?month={month or ""}&page={page_num+1}" class="btn">下一页 →</a>'

    pct = min(round(stocks_done / total_stocks * 100), 99) if total_stocks else 0

    return "text/html", f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ST爬虫监控</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#0f172a;color:#e2e8f0;padding:20px;max-width:1000px;margin:0 auto}}h1{{font-size:22px;margin-bottom:4px;color:#38bdf8}}.sub{{color:#64748b;font-size:13px;margin-bottom:24px}}.card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:16px}}.row{{display:flex;gap:16px;flex-wrap:wrap}}.stat{{flex:1;min-width:120px;text-align:center;padding:16px;background:#0f172a;border-radius:8px}}.stat .num{{font-size:32px;font-weight:700;color:#38bdf8}}.stat .label{{font-size:12px;color:#94a3b8;margin-top:4px}}.bar-wrap{{background:#334155;border-radius:6px;height:24px;margin-top:12px;overflow:hidden}}.bar-fill{{background:linear-gradient(90deg,#0ea5e9,#38bdf8);height:100%;border-radius:6px;transition:width .5s;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;color:#0f172a}}.post{{padding:12px;border-bottom:1px solid #334155}}.post:last-child{{border:none}}.post .title{{color:#e2e8f0;font-size:14px;margin-bottom:6px;line-height:1.5}}.post .meta{{color:#64748b;font-size:12px}}.post .meta span{{margin-right:14px}}.stock-tag{{color:#38bdf8;font-weight:500}}.btn{{display:inline-block;padding:8px 16px;background:#334155;color:#e2e8f0;border-radius:6px;text-decoration:none;margin:4px;font-size:14px}}.btn:hover{{background:#475569}}.btn[disabled]{{opacity:.3;pointer-events:none}}.pagination{{text-align:center;margin-top:16px}}select{{padding:8px 12px;background:#334155;color:#e2e8f0;border:none;border-radius:6px;font-size:14px}}.toolbar{{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px}}@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.5}}}}.live{{display:inline-block;width:8px;height:8px;background:#22c55e;border-radius:50%;margin-right:6px;animation:pulse 2s infinite}}.footer{{text-align:center;color:#475569;font-size:12px;margin-top:16px}}h3{{font-size:15px;color:#94a3b8;margin-bottom:10px}}</style></head>
<body><h1><span class="live"></span>ST 股吧爬虫监控</h1>
<div class="sub">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | SJTU 96核 503GB | 30秒同步{speed_str}</div>

<div class="card"><h3>📊 总体进度</h3>
<div class="row">
<div class="stat"><div class="num">{total_posts:,}</div><div class="label">帖子总数</div></div>
<div class="stat"><div class="num">{stocks_done}/{total_stocks}</div><div class="label">股票完成</div></div>
<div class="stat"><div class="num">{pct}%</div><div class="label">总进度</div></div>
<div class="stat"><div class="num">{elapsed}</div><div class="label">已运行</div></div>
</div>
<div class="bar-wrap"><div class="bar-fill" style="width:{pct}%">{pct}%</div></div>
</div>

<div class="card"><h3>📈 当前: {cur_code} {cur_name}</h3>
<div style="color:#64748b;font-size:13px">当前帖: {cur_posts:,} | 已完成: ~{cur_pages_done} 页 | 远程报: 第{cur_page}页</div>
<div style="color:#94a3b8;font-size:13px;margin-top:4px">最早帖: {earliest} | 最新帖: {latest} | {total_stocks_db} 只股票有数据</div>
</div>

<div class="card"><h3>📅 按年分布</h3>{year_bars}</div>

<div class="card"><h3>🔍 表哥关注</h3><div class="row">{watch_html}</div></div>

<div class="card">
<div class="toolbar"><h3>📋 帖子浏览</h3><form style="display:flex;gap:8px;align-items:center"><select name="month" onchange="location='/?month='+this.value"><option value="">全部月份</option>{month_opts}</select></form></div>
{post_html}
<div class="pagination">{prev_btn} <span style="color:#64748b">第{page_num}页</span> {next_btn}</div>
</div>

<div class="footer">每 30 秒自动同步 | SSH → {SSH_HOST}</div>
<script>setTimeout(function(){{location.reload()}},30000)</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        ct, body = render_page(self.path)
        self.send_response(200); self.send_header("Content-type", f"{ct};charset=utf-8"); self.end_headers()
        self.wfile.write(body.encode())
    def log_message(self,*a): pass

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    print(f"http://localhost:{port}")
    HTTPServer(("0.0.0.0", port), H).serve_forever()
