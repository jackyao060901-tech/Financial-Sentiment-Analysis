# Financial-Sentiment-Analysis

金融社区舆情项目。**第一阶段**目标:广泛摸清各股票社区平台(东方财富股吧、雪球等)
**能不能爬、能的话怎么爬**,并做出能跑的采集原型,为后续的**投资者情绪分析
(Investor Sentiment Analysis)**准备结构化数据。

> 当前阶段只做**数据采集与可行性调研**,不做情绪分析;但字段已按"以后要做情绪分析"设计。

## 目录结构

```
crawlers/            采集脚本
  common.py            共用工具:会话、频率控制、统一字段 CSV
  eastmoney_guba.py    东方财富股吧采集(已跑通,推荐首选)
  sina_finance.py      新浪财经股吧采集(已跑通,GBK 静态页)
  ths_news.py          同花顺个股资讯采集(已跑通,公开 JSON 接口)
  taoguba.py           淘股吧采集(已跑通,个股页+文章页)
  xueqiu.py            雪球采集原型(需 Playwright 过 WAF)
docs/
  feasibility_report.md  各平台爬取可行性报告
  data_schema.md         统一字段设计
data/samples/        采集样本(小)
requirements.txt
```

## 快速开始

```bash
pip install -r requirements.txt

# 抓平安银行(000001)股吧前 3 页,存 CSV
python crawlers/eastmoney_guba.py --code 000001 --pages 3

# 连正文一起抓(较慢)
python crawlers/eastmoney_guba.py --code 600519 --pages 2 --with-body

# 新浪财经股吧(GBK 静态页,symbol 带交易所前缀)
python crawlers/sina_finance.py --symbol sz000001 --pages 2 --with-body

# 同花顺个股资讯(公开 JSON 接口,code 纯数字)
python crawlers/ths_news.py --code 000001 --pages 2

# 淘股吧(个股页+文章页,symbol 带交易所前缀)
python crawlers/taoguba.py --symbol sz000001

# 雪球(需浏览器过 WAF,沙盒跑不了,需本地运行)
python crawlers/xueqiu.py --symbol SZ000001 --pages 1
```

## 各平台可爬性一览

| 平台 | 可爬性 | 需登录/Token | 状态 |
|------|--------|--------------|------|
| 东方财富股吧 | ✅ 高 | 否 | 已做成可跑爬虫 |
| 新浪财经股吧 | ✅ 中 | 否 | 已做成可跑爬虫 |
| 同花顺·资讯 | ✅ 中 | 否 | 已做成可跑爬虫 |
| 淘股吧 | ✅ 中 | 否 | 已做成可跑爬虫 |
| 雪球 | ⚠️ 中低 | 需浏览器 cookie(阿里云 WAF) | 原型就绪,需本地跑 |
| 同花顺·社区帖子 | 🔸 偏难 | 需浏览器/逆向 | 暂缓 |

详见 [`docs/feasibility_report.md`](docs/feasibility_report.md)。

## 路线图

- **第一阶段(当前)**:各平台采集可行性 + 采集原型。
- 第二阶段:在结构化数据上做情绪分析(词典法起步,后续 FinBERT / LLM)。
- 第三阶段:情绪与股价/成交量对比,验证情绪是否有信息量。
