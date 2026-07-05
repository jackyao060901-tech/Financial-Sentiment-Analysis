# Financial-Sentiment-Analysis

**金融社区舆情项目 · 第一阶段:数据源调研与采集框架**
(Data Source Survey & Collection Feasibility Study)

本阶段**不是"写几个爬虫"**,而是一份**股票社区舆情数据源的系统调研**——回答三个问题:

> **① 能不能爬? ② 怎么爬? ③ 研究价值几何(值不值得爬)?**

帮后续的**投资者情绪分析(Investor Sentiment Analysis)** 先踩好坑、选好源。
**成果三件套**:数据源调研报告 + 可运行采集原型 + 技术选型建议。

> 当前阶段**只做数据采集与可行性调研,不做情绪分析**;但字段已按"以后要做情绪分析"设计。
> 🔬 研究诚信:**实测的写"实测",推断的写"判断"**,不用推测代替实验结果。

---

## 一、平台调研一览

| 平台 | 能否爬 | 方式 | 需登录 | 研究价值(散户情绪) | 状态 |
|------|:---:|------|:---:|:---:|------|
| **东方财富股吧** | ✅ | 列表页内嵌 JSON | ✗ | **高** | 已跑通(首选) |
| 淘股吧 | ✅ | 个股页 + 文章页 | ✗ | 较高 | 已跑通 |
| 新浪财经股吧 | ✅ | GBK 静态页 + 详情页 | ✗ | 中低(活跃度低) | 已跑通 |
| 东方财富个股新闻 | ✅ | 公开 JSON + 详情页 | ✗ | 中低(资讯) | 已跑通 |
| 同花顺·个股资讯 | ✅ | 公开 JSON | ✗ | 中低(资讯) | 已跑通 |
| 富途牛牛·资讯 | ✅ | 内嵌 JSON(仅标题) | ✗ | 中低(资讯) | 原型 |
| 百度贴吧 | ✅ | App 接口 + 签名 | ✗ | **低**(个股吧多为公司/产品话题) | 已跑通,但价值低 |
| 雪球 | ⚠️ | 真浏览器过阿里云 WAF | 浏览器 Cookie | 高 | 原型(需本地跑) |
| 同花顺·社区帖子 | ⚠️ | Vue SPA + 签名接口 | 需浏览器/逆向 | 中 | 暂缓 |
| 微博财经 | ⚠️ | 搜索接口需登录 | ✓ | 较高 | 暂缓 |
| 老虎/集思录/知乎/腾讯/格隆汇/金融界/和讯 | 🔸 | 见报告 | — | — | 待遍历 |

详细对比、量化评分、维护成本、选型结论见 **[`docs/feasibility_report.md`](docs/feasibility_report.md)**。

**两个诚实的"踩坑"结论**(方法学价值):
- **雪球**:被新版阿里云 WAF 挡,需真实浏览器;本云沙盒浏览器无法联网,需本地跑。三种方法及局限均已实测记录。
- **百度贴吧**:Web 端 403,换 App 接口+签名后能爬;但实采发现个股同名吧全是招聘/广告/卖货,**不是炒股讨论**——"能爬≠值得爬"的活例子。

---

## 二、目录结构

```
crawlers/                     采集脚本(每平台一个,均已实测)
  common.py                     共用:统一字段 FIELDS / 频率控制+失败重试 / 清洗 / CSV 落盘
  eastmoney_guba.py             东方财富股吧(内嵌 JSON,推荐首选)
  eastmoney_news.py             东方财富个股新闻(公开 JSON + 详情页正文)
  sina_finance.py               新浪财经股吧(GBK 静态页 + 详情页)
  ths_news.py                   同花顺个股资讯(公开 JSON,摘要内嵌)
  taoguba.py                    淘股吧(个股页 + 文章页)
  baidu_tieba.py                百度贴吧(App 接口 + 签名;能爬但内容跑偏)
  futu_news.py                  富途牛牛资讯(内嵌 JSON,仅标题)
  xueqiu.py                     雪球原型(Playwright 过 WAF,需本地跑)
scripts/
  collect_samples.py            一键用统一股票池重建全部平台样本(可复现)
docs/
  feasibility_report.md         数据源调研报告(对比 + 评分 + 选型 + 附录)
  data_schema.md                统一字段设计
  review_package.md             复核包(可整份交叉复核)
data/samples/                   各平台真实样本 CSV(每条带 url + crawl_time)
requirements.txt
```

---

## 三、统一数据字段(schema)

所有平台的采集结果都映射到**同一套字段**(见 `crawlers/common.py` 的 `FIELDS`),便于跨平台合并:

```
platform, stock_code, post_id, title, content, author, author_id,
publish_time, read_count, comment_count, forward_count,
bullish_bearish, has_pic, has_video, url, crawl_time
```

- 做情绪分析至少必须有:`stock_code`、`title`/`content`(文本)、`publish_time`(按天聚合)。
- **拿不到的字段留空,不臆造**;每条带 `url + crawl_time` 可回溯核对。
- 字段逐项说明见 [`docs/data_schema.md`](docs/data_schema.md)。

---

## 四、快速开始

```bash
pip install -r requirements.txt

# —— 单平台采集 ——
# 东方财富股吧(推荐首选);--with-body 连正文一起抓(较慢)
python crawlers/eastmoney_guba.py --code 000001 --pages 3 --with-body

# 新浪财经股吧(GBK 静态页,symbol 带交易所前缀 sz/sh)
python crawlers/sina_finance.py --symbol sz000001 --pages 2 --with-body

# 同花顺个股资讯(公开 JSON,code 纯数字)
python crawlers/ths_news.py --code 000001 --pages 2

# 东方财富个股新闻(公开 JSON + 正文)
python crawlers/eastmoney_news.py --code 000001 --count 10 --with-body

# 淘股吧(个股页 + 文章页)
python crawlers/taoguba.py --symbol sz000001

# 百度贴吧(App 接口;--bar 用公司名/吧名)
python crawlers/baidu_tieba.py --bar 平安银行 --code 000001 --rn 20

# 富途牛牛资讯(内嵌 JSON)
python crawlers/futu_news.py --code 000001

# 雪球(需真浏览器过 WAF,本云沙盒跑不了,需本地运行)
python crawlers/xueqiu.py --symbol SZ000001 --pages 1

# —— 一键重建全部平台样本 ——
python scripts/collect_samples.py
```

---

## 五、合规与礼貌

- 所有请求带**随机延时 + 失败重试**(`common.polite_get`),控制频率、不影响目标站。
- 数据**仅用于研究/课程用途**。
- 凭据(如需)从环境变量读取,**不在源码硬编码**。

## 六、路线图

- **第一阶段(当前)**:各平台采集可行性 + 采集原型 + 数据源选型建议。
- 第二阶段:在结构化数据上做情绪分析(词典法起步 → FinBERT / LLM)。
- 第三阶段:情绪与股价/成交量对比,验证情绪是否有信息量。
