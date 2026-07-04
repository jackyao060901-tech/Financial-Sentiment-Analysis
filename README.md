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

# 雪球(需浏览器过 WAF)
python crawlers/xueqiu.py --symbol SZ000001 --pages 1
```

## 各平台可爬性一览

| 平台 | 可爬性 | 需登录/Token | 状态 |
|------|--------|--------------|------|
| 东方财富股吧 | ✅ 高 | 否 | 已做成可跑爬虫 |
| 雪球 | ⚠️ 中低 | 需浏览器 cookie(阿里云 WAF) | Playwright 原型 |
| 新浪财经 / 同花顺 / 淘股吧 | 🔸 待深入 | 部分需 | 初步评估 |

详见 [`docs/feasibility_report.md`](docs/feasibility_report.md)。

## 路线图

- **第一阶段(当前)**:各平台采集可行性 + 采集原型。
- 第二阶段:在结构化数据上做情绪分析(词典法起步,后续 FinBERT / LLM)。
- 第三阶段:情绪与股价/成交量对比,验证情绪是否有信息量。
