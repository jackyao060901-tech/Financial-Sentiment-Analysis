# 股吧 + 雪球 反反爬技术评估

## 结论

**我们的场景不需要 Selenium，不需要 IP 池。** 300 只 ST 股 × 1-2 页/天 = 正常人刷论坛水平。但万一被封需要备选方案。以下是完整技术评估。

---

## 1. Selenium/Playwright（浏览器自动化）

### 原理
```
requests:  HTTP GET → 拿 HTML 源码
Selenium:  启动 Chrome → 渲染 JS → 模拟真实用户
```

### 评估

| | requests（我们现在） | Selenium/Playwright |
|---|---|---|
| EastMoney 股吧 | ✅ 完美。数据嵌在 HTML JSON 里 | ❌ 不需要。浪费 10 倍资源 |
| 雪球 | ⚠️ Cookie 认证麻烦 | ✅ 浏览器自动处理 Cookie |
| 速度 | 0.3s/页 | 3-5s/页（启动浏览器+渲染） |
| 反检测 | 需要伪装 Headers | 天然像真人 |
| 资源占用 | 几 MB 内存 | 500MB+ 内存/实例 |

### 什么时候用 Selenium

```
✗ 股吧：数据是 JSON 嵌在 HTML 里的，requests 直接拿 → 不需要 Selenium
✗ 日常增量：请求量太低，不会被封 → 不需要 Selenium  
✓ 雪球：Cookie 管理复杂时，Selenium 自动处理登录态
✓ 被封后的应急：Chrome 指纹比 requests 难检测
```

**结论：Selenium 是备选，不是首选。** 我们现在的 requests 方案对股吧完全够用。雪球可以加一个 Selenium fallback。

---

## 2. 间隔时间（请求频率控制）

### 什么是"安全间隔"

```
正常用户行为分析:
  打开股吧首页 → 浏览 2-5s → 点进帖子 → 阅读 10-30s → 翻页 → 浏览 2-5s
  
模拟策略:
  - 页间延时 2-3s（翻页）
  - 股间延时 5-8s（换股票）
  - 随机 ±50% 抖动（避免机器节律）
```

### 我们的实际需求 vs 阈值

```
EastMoney 反爬阈值:
  单小时 >600 次 → 验证码
  单天 >2000 次  → 封锁

我们的请求量:
  300 只 ST × 1 页 × 2 次/天 = 600 次/天  ← 全天总量
  600 / 24h = 25 次/小时                     ← 远低于 600/小时的阈值
  
  即使: 300 只 × 3 页 × 1 次 = 900 次/天
  分散到 2 小时: 450 次/小时                  ← 仍低于阈值
```

**安全建议：**
```
日常:    页间 1-3s 随机, 股间 3-5s 随机    ← 我们已在用 (delay=0.3s → 改为 2s)
初次补历史: 页间 3-5s, 股间 8-12s           ← 给服务器预留缓冲
紧急恢复:  页间 8-15s, 股票间 30s+           ← 最坏情况
```

### Python 实现

```python
import time, random

def human_delay(min_s=1.0, max_s=3.0):
    """模拟人类浏览间隔"""
    time.sleep(random.uniform(min_s, max_s))

def stock_delay():
    """换股票时的间隔（读一下刚才的数据）"""
    human_delay(3.0, 8.0)

def page_delay():
    """翻页时的间隔"""
    human_delay(1.0, 3.0)
```

---

## 3. IP 池（IP Pool）

### 原理
```
单 IP:     ──[请求1]──[请求2]──[请求3]── → 频率高 → 封
IP 池:     IP1: ──[请求1]──────────────
           IP2: ────────[请求2]───────── → 分散流量
           IP3: ───────────────[请求3]──
```

### 评估

| 方案 | 费用 | 稳定性 | 适用场景 |
|------|:---:|:---:|------|
| 免费代理 | ¥0 | ❌ 极不稳定 | 学习测试 |
| 付费代理池（快代理/芝麻） | ¥100-500/月 | ✅ 稳定 | 万级请求/天 |
| 自建 ADSL 拨号池 | ¥200/月 | ✅ | 十万级请求/天 |
| 国内云服务器多台 | ¥50×N/月 | ✅ | 分散地域 |
| **不需要** | **¥0** | **✅** | **我们的场景** |

### 我们的请求量需要 IP 池吗？

```
我们:     600-900 次/天  → 不需要 IP 池
需要:     >5,000 次/天   → 考虑 IP 池
一定需要: >10,000 次/天  → 必须 IP 池

单 IP 正常用户一天刷 100-200 次是常态
我们在 600-900 次，稍高但可接受
加合理延时后完全安全
```

### 如果以后要加 IP 池

```python
# 轻量方案：2-3 个固定代理轮询
PROXIES = [
    "http://user:pass@proxy1:8080",
    "http://user:pass@proxy2:8080",
    "http://user:pass@proxy3:8080",
]

def get_with_proxy(url):
    proxy = random.choice(PROXIES)
    return requests.get(url, proxies={"http": proxy, "https": proxy})
```

---

## 4. 其他反反爬技巧

### User-Agent 轮换
```python
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/119.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Edge/120.0.0.0",
]
```

### Referer 链
```python
# 先访问股吧首页 → 再访问个股页（模拟正常浏览路径）
session.get("https://guba.eastmoney.com/")
time.sleep(1)
session.get(f"https://guba.eastmoney.com/list,{code}.html")
```

### Cookie 预热
```python
# 第一次访问拿 Cookie
session.get("https://www.eastmoney.com/")  # 东方财富主页
time.sleep(2)
session.get("https://guba.eastmoney.com/")  # 股吧首页
# Cookie 里有浏览记录，更像真人
```

---

## 5. 三平台最终方案

| | 东方财富股吧 | 雪球 | 小红书 |
|---|---|---|---|
| 数据获取 | `requests` 解析 HTML JSON | `requests` + Cookie 维护 + API | ❌ 不做 |
| 反爬等级 | 🟡 中 | 🟡 中 | 🔴 极高 |
| 需要 Selenium | ❌ 不需要 | ⚠️ 备选 | ✅ 必须 |
| 需要 IP 池 | ❌ 不需要 | ❌ 不需要 | ✅ 必须 |
| 安全日请求量 | <2,000 | <500 | N/A |
| 延时策略 | 页间 1-3s, 股间 3-5s | 页间 3-5s, 股间 5-10s | N/A |

---

## 6. 被封后的应急方案

```
Level 1: 延时 ×3, 继续用 requests
Level 2: 换 User-Agent + Cookie 预热
Level 3: 上 Selenium (headless Chrome + stealth.js)
Level 4: 上 IP 代理池
Level 5: 暂停 24h, 换 IP 重新开始
```

**大概率永远用不到 Level 2 以后。** 300 只 ST 股的请求量就是正常用户水平。
