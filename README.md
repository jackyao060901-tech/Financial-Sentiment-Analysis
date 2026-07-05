# Financial-Sentiment-Analysis

金融社区舆情项目。**第一阶段定位 = 数据源调研与采集框架**:
不是"写几个爬虫",而是一份**股票社区舆情数据源地图**——回答三个问题
**① 能不能爬 ② 怎么爬 ③ 值不值得爬**,帮后续的**投资者情绪分析
(Investor Sentiment Analysis)** 先踩好坑、选好源。

**成果三件套**:数据源调研报告 + 可运行采集原型 + 技术选型建议。

> 当前阶段只做**数据采集与可行性调研**,不做情绪分析;但字段已按"以后要做情绪分析"设计。
> 平台横向对比、维护成本、量化评分见 [`docs/feasibility_report.md`](docs/feasibility_report.md)。

## 目录结构

```
crawlers/            采集脚本
  common.py            共用工具:会话、频率控制+失败重试、清洗、统一字段 CSV
  eastmoney_guba.py    东方财富股吧采集(已跑通,推荐首选)
  eastmoney_news.py    东方财富个股新闻采集(已跑通,公开 JSON 接口)
  sina_finance.py      新浪财经股吧采集(已跑通,GBK 静态页)
  ths_news.py          同花顺个股资讯采集(已跑通,公开 JSON 接口)
  taoguba.py           淘股吧采集(已跑通,个股页+文章页)
  xueqiu.py            雪球采集原型(需 Playwright 过 WAF,需本地跑)
scripts/
  collect_samples.py   一键重建全部平台样本(可复现)
docs/
  feasibility_report.md  各平台爬取可行性报告(含执行摘要、局限)
  data_schema.md         统一字段设计
  review_package.md      复核包(可整份交叉复核)
data/samples/        真实采集样本(5 平台,共约 230 条,5 只股票)
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

# 东方财富个股新闻(公开 JSON 接口,code 纯数字)
python crawlers/eastmoney_news.py --code 000001 --count 10 --with-body

# 淘股吧(个股页+文章页,symbol 带交易所前缀)
python crawlers/taoguba.py --symbol sz000001

# 雪球(需浏览器过 WAF,沙盒跑不了,需本地运行)
python crawlers/xueqiu.py --symbol SZ000001 --pages 1

# 一键重建全部平台样本
python scripts/collect_samples.py
```

## 各平台可爬性一览

| 平台 | 可爬性 | 需登录/Token | 状态 |
|------|--------|--------------|------|
| 东方财富股吧 | ✅ 高 | 否 | 已做成可跑爬虫 |
| 东方财富个股新闻 | ✅ 高 | 否 | 已做成可跑爬虫 |
| 新浪财经股吧 | ✅ 中 | 否 | 已做成可跑爬虫 |
| 同花顺·资讯 | ✅ 中 | 否 | 已做成可跑爬虫 |
| 淘股吧 | ✅ 中 | 否 | 已做成可跑爬虫 |
| 雪球 | ⚠️ 中低 | 需浏览器 cookie(阿里云 WAF) | 原型就绪,需本地跑 |
| 同花顺·社区帖子 | 🔸 偏难 | 需浏览器/逆向 | 暂缓 |
| 微博 / 金融界 / 和讯 | ⚠️/❌ | 微博搜索需登录;金融界·和讯本环境不可达 | 调研记录,暂缓 |

详见 [`docs/feasibility_report.md`](docs/feasibility_report.md)。

## 路线图

- **第一阶段(当前)**:各平台采集可行性 + 采集原型。
- 第二阶段:在结构化数据上做情绪分析(词典法起步,后续 FinBERT / LLM)。
- 第三阶段:情绪与股价/成交量对比,验证情绪是否有信息量。
