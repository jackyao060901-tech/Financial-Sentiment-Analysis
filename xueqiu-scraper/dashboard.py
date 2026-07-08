"""雪球采集实时看板 —— 仿老师 ST Guba Scraper 的形式。

读 SQLite(xueqiu.db)实时展示:总帖数、每只股票进度(日期范围/条数/是否到2020)、
最新抓取的帖子(LIVE feed),并支持下载 CSV。爬虫在跑,这个网页自动刷新看进度。

跑法:
  pip install flask
  python dashboard.py                 # 默认读 data/xueqiu.db,开 http://127.0.0.1:8000
  # 想像老师那样对外分享,用内网穿透(任选其一):
  #   ssh -R 80:localhost:8000 serveo.net        (serveo,和老师一样)
  #   或  cloudflared tunnel --url http://localhost:8000
"""
import os
import csv
import io
import sqlite3
import argparse
import datetime

from flask import Flask, jsonify, Response

DB = os.environ.get("XQ_DB", "data/xueqiu.db")
SINCE = "2020-01-01"
# 展示用的股票顺序/名称(与爬虫 STOCKS 对应)
WATCH = [("SZ300301", "ST长方"), ("SZ002816", "ST和科"), ("SH688646", "ST逸飞"),
         ("SH688076", "ST诺泰"), ("SZ002055", "ST得润")]
START = datetime.datetime.now()
app = Flask(__name__)


def q(db, sql, args=()):
    return db.execute(sql, args).fetchall()


def build_data():
    if not os.path.exists(DB):
        return {"total": 0, "stocks": [], "feed": [], "done": 0, "err": "DB 未生成,先跑 xueqiu_scraper.py"}
    db = sqlite3.connect(DB)
    total = q(db, "SELECT COUNT(*) FROM posts")[0][0]
    stocks, done = [], 0
    for sym, name in WATCH:
        row = q(db, "SELECT COUNT(*), MIN(created_at), MAX(created_at) FROM posts WHERE symbol=?", (sym,))[0]
        cnt, earliest, latest = row[0], (row[1] or "")[:10], (row[2] or "")[:10]
        reached = bool(earliest) and earliest < SINCE
        done += reached
        stocks.append({"symbol": sym, "name": name, "count": cnt,
                       "earliest": earliest or "--", "latest": latest or "--",
                       "yr_span": f"{earliest[:4]}-{latest[:4]}" if earliest else "--",
                       "reached": reached})
    stocks.sort(key=lambda s: -s["count"])
    feed = [{"stock": r[0], "time": (r[1] or "")[:10], "title": (r[2] or r[3] or "")[:60]}
            for r in q(db, "SELECT stock_name, created_at, title, text FROM posts "
                           "ORDER BY crawl_time DESC, created_at DESC LIMIT 12")]
    db.close()
    return {"total": total, "stocks": stocks, "feed": feed, "done": done, "target": len(WATCH)}


@app.route("/data")
def data():
    return jsonify(build_data())


@app.route("/uptime")
def uptime():
    s = int((datetime.datetime.now() - START).total_seconds())
    return f"运行 {s//3600}h {s%3600//60}m"


@app.route("/download")
def download():
    if not os.path.exists(DB):
        return "DB 未生成", 404
    db = sqlite3.connect(DB)
    cols = [c[1] for c in db.execute("PRAGMA table_info(posts)")]
    buf = io.StringIO(); w = csv.writer(buf); w.writerow(cols)
    w.writerows(db.execute(f"SELECT {','.join(cols)} FROM posts ORDER BY symbol, created_at"))
    db.close()
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=xueqiu_all.csv"})


@app.route("/")
def index():
    return HTML


HTML = """<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Xueqiu ST Scraper</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0b1120;color:#e2e8f0}
.container{max-width:1200px;margin:0 auto;padding:32px 24px}
.header{text-align:center;margin-bottom:28px}
.header h1{font-size:1.8rem;font-weight:700;letter-spacing:-.5px}
.header .sub{color:#64748b;font-size:.85rem;margin-top:6px}
.live-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#10b981;margin-right:5px;animation:pulse 1.5s infinite}
@keyframes pulse{50%{opacity:.3}}
.summary{display:flex;gap:14px;flex-wrap:wrap;justify-content:center;margin-bottom:24px}
.kpi{background:#111a2e;border:1px solid #1e293b;border-radius:12px;padding:18px 26px;text-align:center;min-width:150px}
.kpi .num{font-size:2rem;font-weight:800;font-variant-numeric:tabular-nums}
.kpi .lbl{color:#64748b;font-size:.72rem;margin-top:4px}
.live-feed{background:#0f1729;border:1px solid #1e293b;border-radius:12px;padding:16px 18px;margin-bottom:24px}
.feed-title{color:#38bdf8;font-size:.8rem;font-weight:700;margin-bottom:10px}
.feed-item{font-size:.8rem;padding:4px 0;color:#cbd5e1;border-bottom:1px solid #16203400}
.feed-stock{color:#38bdf8;font-weight:600;margin-right:8px}
.feed-time{color:#64748b;margin-right:8px;font-variant-numeric:tabular-nums}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px}
.card{background:#111a2e;border:1px solid #1e293b;border-radius:12px;padding:18px}
.card-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.stock-name{font-size:1.1rem;font-weight:700}
.stock-code{color:#64748b;font-size:.8rem;margin-left:8px}
.badge{font-size:.62rem;font-weight:700;padding:3px 9px;border-radius:20px}
.badge.done{background:#10321f;color:#34d399}
.badge.miss{background:#3a2416;color:#fbbf24}
.date-line{display:flex;align-items:center;gap:8px;font-size:.78rem;color:#94a3b8;margin-bottom:8px;font-variant-numeric:tabular-nums}
.arrow{color:#475569}
.metrics{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px}
.metric{background:#0b1120;border-radius:8px;padding:12px;text-align:center}
.m-val{font-size:1.3rem;font-weight:800;font-variant-numeric:tabular-nums}
.m-lbl{color:#64748b;font-size:.65rem;margin-top:2px}
.footer{text-align:center;color:#475569;font-size:.75rem;margin-top:24px}
a{color:#38bdf8}
</style></head><body><div class="container">
<div class="header"><h1>Xueqiu ST Scraper</h1>
<div class="sub"><span class="live-dot"></span><span id="cur">雪球讨论帖采集</span> · <span id="tick">--</span></div></div>
<div class="summary">
  <div class="kpi"><div class="num" id="total" style="color:#34d399">--</div><div class="lbl">帖子总数</div></div>
  <div class="kpi"><div class="num" id="done" style="color:#38bdf8">--</div><div class="lbl">已回溯到 2020</div></div>
  <div class="kpi"><a href="/download" style="font-size:1.2rem;font-weight:700">下载 CSV</a><div class="lbl">全部数据</div></div>
</div>
<div class="live-feed"><div class="feed-title">LIVE 最新抓取</div><div id="feed"></div></div>
<div class="grid" id="grid"></div>
<div class="footer" id="uptime">--</div></div>
<script>
async function load(){
  try{
    const d = await (await fetch("/data")).json();
    document.getElementById("total").textContent = (d.total||0).toLocaleString();
    document.getElementById("done").textContent = (d.done||0)+" / "+(d.target||0);
    document.getElementById("feed").innerHTML = (d.feed||[]).map(f=>
      '<div class="feed-item"><span class="feed-stock">'+f.stock+'</span><span class="feed-time">'+f.time+'</span>'+
      (f.title||'').replace(/</g,'&lt;')+'</div>').join('') || '<div class="feed-item" style="color:#64748b">暂无数据,先运行爬虫</div>';
    document.getElementById("grid").innerHTML = (d.stocks||[]).map(s=>
      '<div class="card"><div class="card-header"><div><span class="stock-name">'+s.name+'</span>'+
      '<span class="stock-code">'+s.symbol+'</span></div>'+
      (s.reached?'<span class="badge done">到2020</span>':'<span class="badge miss">最早 '+s.earliest+'</span>')+'</div>'+
      '<div class="date-line"><span>'+s.earliest+'</span><span class="arrow">→</span><span>'+s.latest+'</span>'+
      '<span style="margin-left:auto;color:#64748b">'+s.yr_span+'</span></div>'+
      '<div class="metrics"><div class="metric"><div class="m-val" style="color:#38bdf8">'+(s.count||0).toLocaleString()+
      '</div><div class="m-lbl">帖子数</div></div>'+
      '<div class="metric"><div class="m-val" style="color:'+(s.reached?'#34d399':'#fbbf24')+'">'+
      (s.reached?'✓':'…')+'</div><div class="m-lbl">2020 目标</div></div></div></div>').join('');
    if(d.err) document.getElementById("cur").textContent = d.err;
  }catch(e){}
}
async function up(){ try{ document.getElementById("uptime").textContent = await (await fetch("/uptime")).text(); }catch(e){} }
let n=0; setInterval(()=>{document.getElementById("tick").textContent = (n++)+"s";},1000);
load(); up(); setInterval(load,5000); setInterval(up,30000);
</script></body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB)
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    DB = a.db
    app.run(host="0.0.0.0", port=a.port)
