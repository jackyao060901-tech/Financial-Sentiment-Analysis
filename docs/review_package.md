# 复核包(Review Package)—— 给交叉复核用

> **用途**:本文件是一份自包含的项目复核材料,可整份贴给另一个大模型(如 GPT)做交叉审查。
> 请审查者重点看最后一节「请复核的具体问题」。
> **当前阶段**:金融社区舆情项目的**第一阶段 = 数据采集与各平台爬取可行性调研**;**本阶段不做情绪分析**。

---

## 1. 背景与目标

- **项目中心**:采集股票社区(东方财富股吧、雪球等)的舆情数据,为后续**投资者情绪分析
  (Investor Sentiment Analysis)** 打基础。
- **导师原话(需求来源)**:
  > "调研一下,雪球、东方财富股吧上面的帖子、文章,看看怎么用爬虫可以爬下来。这个对金融的舆情分析很重要。舆情分析本身也是 data science 里的一个课题。"
  > 补充确认:"目前是拿数据就行,分析是后面的。"
- **因此第一阶段的任务** = 广泛摸清各平台**能不能爬、能的话怎么爬**,做出**能跑的采集原型**,并把字段按"以后要做情绪分析"设计好。**不在本阶段做情绪分析。**
- **质量四要求**:准确性、可读性、导师认可度、真实性。**数据必须真实抓取,不得用模型记忆编造**;拿不到的字段留空,不臆造;每条数据带 `url + crawl_time` 可回溯。

## 2. 成果概览(第一阶段)

- **共调研 10 个平台/入口,5 个已做成可跑爬虫**,并采到**真实、带正文**的样本:
  1. 东方财富股吧(`eastmoney_guba.py`)
  2. 东方财富个股新闻(`eastmoney_news.py`)
  3. 新浪财经股吧(`sina_finance.py`)
  4. 同花顺个股资讯(`ths_news.py`)
  5. 淘股吧(`taoguba.py`)
- **雪球**(`xueqiu.py`):爬虫原型就绪,但被新版阿里云 WAF 挡住,需真实浏览器,且**本云沙盒浏览器无法联网**,需本地运行。
- 样本落在 `data/samples/`,用统一股票池(平安银行/贵州茅台/宁德时代/海康威视/中国平安)采集,覆盖不同行业与大小盘。

## 3. 各平台技术方法与结论(核心)

| 平台 | 能否爬 | 怎么爬(关键) | 登录/Token | 能拿到的字段 |
|------|--------|----------------|------------|--------------|
| 东方财富股吧 | ✅ | 列表页内嵌 `var article_list={...}` JSON,每页约80条;正文去详情页 | 否 | 标题/正文/作者/时间(带年)/阅读/评论/转发/看涨看跌标记 |
| 东方财富个股新闻 | ✅ | `np-listapi.eastmoney.com` 公开 JSON;正文在详情页 `id=ContentBody` | 否 | 标题/正文/时间/链接 |
| 新浪财经股吧 | ✅ | GBK 静态表格(阅读\|评论\|标题\|作者\|时间);正文详情页 `id=thread_content` | 否 | 标题/正文/作者/阅读/评论/时间(仅月日) |
| 同花顺个股资讯 | ✅ | `news.10jqka.com.cn` 公开 JSON,`digest` 摘要内嵌 | 否 | 标题/摘要/来源/时间/链接 |
| 淘股吧 | ✅ | 个股页 `related-subject` 取帖 → 文章页取正文与元数据 | 否 | 标题/正文/作者/时间(带年)/浏览/评论 |
| 雪球 | ⚠️ | **新版阿里云 WAF(JS-VM 挑战)**,需真浏览器过关(见下) | 需浏览器 cookie | 标题/正文/作者/时间/阅读评论转发 |
| 同花顺社区帖子 | ⚠️ | Vue SPA + axios + md5,接口疑带签名;老 guba 域 503 | 需浏览器/逆向 | — |
| 微博 | ⚠️ | 访客 cookie 能拿,但**搜索接口返回需登录**(`ok:-100`→sso) | 搜索需登录 | — |
| 金融界 / 和讯 | ❌ | 本云环境**代理连接失败,不可达** | — | — |

### 雪球的三种方法与结论(已实测)
- **方法一 · 真浏览器(Playwright)= 推荐**:真执行 WAF 的 JS 通过挑战,**稳**(WAF 升级也自动跟上)。局限:本沙盒 headless Chromium 穿不过出网代理(连 example.com 都 `ERR_CONNECTION_RESET`),故需**本地/普通网络机器**跑。
- **方法二 · 纯 requests = 不通**:不执行 JS,只拿到 WAF 挑战页。
- **方法三 · 无浏览器执行挑战 JS / 逆向 WAF = 实测跑不通、不推荐**:裸 Node 报 `document is not defined`;jsdom 只跑一半、算不出放行 cookie、卡在需真实页面跳转;且新版 WAF 靠浏览器指纹+导航,逆向极脆弱(反爬军备竞赛)。

## 4. 关键决策与取舍(请重点审查是否合理)

1. **先采集、不分析**:严格按导师"先拿数据"。分析放第二阶段。
2. **主攻东方财富股吧**:无需登录、字段最全、量大、纯散户,最贴合"散户舆情"。
3. **字段先对齐后续分析**:即使现在不分析,也把 `title/content/publish_time/stock_code` 等存好,避免"爬了没法用"。
4. **雪球不在沙盒硬啃**:真浏览器跑不通是环境限制,逆向 WAF 太脆;决定留给本地跑,不浪费在军备竞赛上。
5. **同花顺分两块**:资讯(公开 JSON,易)先做;社区帖子(签名 SPA,难)暂缓。
6. **文本只做轻清洗**:去标签/解码实体/压空白;股票标记与表情占位符**保留**(是否清洗留给分析阶段按需决定,避免过早丢信息)。
7. **下一阶段情绪分析路线设想**:词典法起步(中文金融情感词典 + jieba,可解释、零依赖)→ 需要精度再上 FinBERT 中文版 →(可选)LLM 打标。

## 5. 统一数据字段(schema)

所有平台映射到同一套字段(见 `crawlers/common.py` 的 `FIELDS`),便于跨平台合并:

```
platform, stock_code, post_id, title, content, author, author_id,
publish_time, read_count, comment_count, forward_count,
bullish_bearish, has_pic, has_video, url, crawl_time
```

- 做情绪分析至少必须有:`stock_code`、`title`/`content`(文本)、`publish_time`(按天聚合)。
- 拿不到的字段留空,不臆造。

## 6. 已知局限(诚实记录)

1. 样本是**原型级**(每平台每股十余条),非全量。
2. 时间格式不统一:**新浪仅"MM月DD日"无年份**,已原样保留,合并前需归一化。
3. "资讯" vs "散户帖子":同花顺资讯/东财新闻无阅读评论数,情绪属性不同,需区分。
4. 未做跨源去重/转载识别。
5. 文本仅轻清洗,保留股票标记与表情。
6. 爬虫依赖页面结构,易碎,需定期维护。

## 7. 代码结构

```
crawlers/
  common.py            统一字段 FIELDS / 频率控制+失败重试 polite_get / clean_text / save_csv
  eastmoney_guba.py    东方财富股吧(内嵌JSON)
  eastmoney_news.py    东方财富个股新闻(公开JSON+详情页)
  sina_finance.py      新浪财经股吧(GBK静态页+详情页)
  ths_news.py          同花顺个股资讯(公开JSON)
  taoguba.py           淘股吧(个股页+文章页)
  xueqiu.py            雪球原型(Playwright过WAF,需本地)
scripts/collect_samples.py   一键重建全部样本(可复现)
docs/feasibility_report.md   各平台可行性详报
docs/data_schema.md          字段设计
data/samples/*.csv           真实样本
```

**关键代码片段(供无仓库时审查):**

```python
# common.py —— 礼貌请求 + 失败重试(应对代理抖动)
def polite_get(session, url, referer=None, timeout=20,
               min_delay=1.0, max_delay=2.5, retries=3, **kwargs):
    if referer:
        kwargs.setdefault("headers", {}).setdefault("Referer", referer)
    last_err = None
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=timeout, **kwargs)
            time.sleep(random.uniform(min_delay, max_delay))  # 频率控制
            return resp
        except requests.RequestException as e:
            last_err = e
            time.sleep(2 ** attempt)  # 指数退避
    raise last_err
```

```python
# eastmoney_guba.py —— 从列表页内嵌 JSON 抠数据(大括号配平,稳)
def _extract_article_list(html):
    idx = html.find("var article_list")
    if idx == -1: return None
    start = html.find("{", idx); depth = 0
    for i in range(start, len(html)):
        if html[i] == "{": depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(html[start:i+1])
    return None
```

---

## 8. 请复核的具体问题(审查者重点看这里)

请从以下角度审查,并**指出错误、盲点、更优做法**:

1. **技术判断准确性**:雪球=新版阿里云 WAF 需真浏览器、同花顺社区=签名 SPA、微博搜索=需登录 —— 这些结论是否正确?有没有我误判、其实有更简单可行路径的?
2. **平台覆盖**:对**A 股散户舆情**这个目标,平台选择是否合理?**有没有更好、更易爬、信息量更大的中文源被我漏掉**(例如富途、格隆汇、老虎、贴吧、知乎财经等)?
3. **字段设计**:这套统一字段对后续「投资者情绪分析」是否够用?**还缺什么关键字段**(如点赞、IP归属、是否原创、情绪标签等)?
4. **数据真实性与可回溯**:带 `url+crawl_time`、字段留空不臆造 —— 这套做法是否足以支撑"数据真实、可核对"?
5. **合规与礼貌**:随机延时 + 失败重试 + 仅研究用途 —— 是否到位?有无法律/条款风险需提醒?
6. **代码质量与健壮性**:解析方式(内嵌 JSON / 正则 / GBK 编码 / 大括号配平)有无明显脆弱点或更稳的写法?
7. **阶段划分**:第一阶段只做采集、把雪球留给本地、同花顺社区暂缓 —— 范围是否恰当?有没有过度或不足?
8. **下一阶段路线**:情绪分析"词典法→FinBERT→LLM"的递进是否合理?对中文金融文本,起步用哪种更稳?
