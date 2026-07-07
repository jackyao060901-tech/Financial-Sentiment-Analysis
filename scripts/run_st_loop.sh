#!/usr/bin/env bash
# 自动循环:跑整合采集器 → 导出 → 提交推送 → 判断是否 5 只都到2020 → 冷却续跑。
# 全自动,直到全部回溯到 2020 或达到最大轮数。
cd "$(dirname "$0")/.." || exit 1
BR=claude/financial-sentiment-analysis-w29uv5
DONE_CHECK='import sqlite3;d=sqlite3.connect("data/st_guba.db");print(sum(1 for c in ["300301","002816","688646","688076","002055"] if (d.execute("SELECT MIN(publish_time) FROM posts WHERE stock_code=?",(c,)).fetchone()[0] or "9999")<"2020-01-01"))'
for iter in $(seq 1 40); do
  echo "===== 循环 $iter 开始 $(date +%H:%M:%S) ====="
  python3 scripts/collect_st_guba.py --threads 3 --pmin 3 --pmax 5 --empty-limit 8 --since 2020-01-01
  python3 scripts/collect_st_guba.py --export
  git add data/st_since2020/*.csv 2>/dev/null
  git commit -q -m "data(ST): 自动循环采集快照 iter$iter" 2>/dev/null && \
    for r in 1 2 3 4; do git push -q origin "$BR" && break || sleep $((2**r)); done
  DONE=$(python3 -c "$DONE_CHECK")
  TOT=$(python3 -c "import sqlite3;print(sqlite3.connect('data/st_guba.db').execute('SELECT COUNT(*) FROM posts').fetchone()[0])")
  echo "循环 $iter 结束: 到2020的股票 $DONE/5, DB合计 $TOT 条"
  if [ "$DONE" = "5" ]; then echo "ALLDONE_5_STOCKS_REACHED_2020"; break; fi
  echo "...冷却 240s 让 IP 恢复..."
  sleep 240
done
echo "ST_LOOP_END"
