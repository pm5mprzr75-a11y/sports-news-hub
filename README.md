# 体育新闻聚合 · 筛选 · 评论抓取工具

抓取主流体育媒体近 7 天内容，按"体育产业"关键词自动打标与筛选，查看新闻评论，并导出 Excel / CSV / PDF 报告。

## 功能
- **主流站点 + 社交平台聚合**：新浪/网易/搜狐/央视/新华/人民网体育、ESPN/BBC/Guardian、虎扑、直播吧；社交层含**微博**、**百度贴吧**（按运动项目检索 UGC 内容）。
- **近 7 天窗口**：默认近 7 天，可切换 1/3/7/14/30 天。
- **体育产业关键词引擎**：预设"体育产业 / 竞赛赛事 / 体育版权 / 赞助营销 / 俱乐部球队 / 媒体平台 / 政策资本"分类，自动打标；支持自定义关键词。
- **运动项目维度**：`config/sports.yaml` 内置 18 个运动分类（篮球/足球/跑步/健身/游泳/羽毛球/乒乓/网球/排球/骑行/滑雪/瑜伽/电竞/登山徒步/钓鱼/格斗/台球/马拉松），所有文章自动打"运动标签"，界面可按运动筛选。
- **关键词搜索 + 产业分类筛选 + 运动项目筛选 + 来源筛选 + 仅看有评论**。
- **评论抓取**（best-effort）：虎扑、微博热评、百度贴吧楼层回复；其余标注"暂不支持"，不阻塞。
- **导出**：Excel（含「评论明细」工作表）/ CSV / PDF；另可单独导出评论 Excel/CSV。

## 快速开始
```bash
# 1) 依赖已装入虚拟环境（见 requirements.txt）
# 2) 初始化并抓取（近 7 天）
python scheduler/run_crawl.py

# 3) 启动 Web 界面
streamlit run app.py
# 浏览器打开 http://localhost:8501
```
> 若 streamlit 未全局安装，用虚拟环境：`.venv/bin/streamlit run app.py`（本项目已使用 managed venv）。

## 目录结构
```
config/        sources.yaml（站点注册表） + keywords.yaml（关键词词典） + sports.yaml（运动分类）
crawlers/      适配器（rss / json_api / html / weibo / tieba）+ comments/（网易/虎扑/微博/贴吧）
store/         SQLite + FTS5 存储
nlp/           关键词匹配引擎
export/        Excel / CSV / PDF 导出
scheduler/     run_crawl.py 抓取入口（可定时）
app.py         Streamlit 界面
data/          生成的 sports_news.db
exports/       导出的报告
```

## 添加站点 / 关键词
- **加站点**：编辑 `config/sources.yaml`，复制一项改 `id/name/url`，`enabled: true` 即可；type 支持 `rss | json_api | html | weibo | tieba`。
- **加关键词**：界面左侧"自定义关键词"实时添加；或在 `config/keywords.yaml` 的对应分类下追加词条。
- **加运动项目**：编辑 `config/sports.yaml`，每项含 `name / keywords / tieba`（贴吧吧名）；微博与贴吧适配器会据此自动检索与打标。

## 接入自有 Cookie（微博被 SSO 拦截时）
若微博在本机仍返回空，可登录 m.weibo.cn 后从浏览器开发者工具复制 `SUB`/`SUBP` cookie，在 `config/sources.yaml` 的 `weibo_sports` 下新增字段（需代码支持读取，见 `crawlers/weibo_adapter.py` 的 `_ensure_visitor`）。贴吧若为 403，可补充 `BAIDUID` cookie。

## 定时抓取（保持 7 天窗口新鲜）

已内置 `scheduler/cron_run.sh` 包装脚本（绝对路径、自动写日志到 `data/crawl.log`）。三种方式任选：

**方式 A · macOS launchd（推荐，重开机也在、不依赖 WorkBuddy）**
项目已附带 `~/Library/LaunchAgents/com.sportsnews.hub.plist`，每天 **03:00** 触发一次，加载即立即跑一次：
```bash
# 加载（仅首次需要）
launchctl load ~/Library/LaunchAgents/com.sportsnews.hub.plist
# 查看是否加载成功
launchctl list | grep com.sportsnews.hub
# 卸载（不再自动抓取）
launchctl unload ~/Library/LaunchAgents/com.sportsnews.hub.plist
```
> 想改时间：编辑 plist 里的 `StartCalendarInterval`（Hour/Minute），保存后 `unload` 再 `load`。

**方式 B · crontab**
```bash
crontab -e
# 每天 03:00 抓取（替换为你自己的 venv python 绝对路径）
0 3 * * * /Users/yoyo/.workbuddy/binaries/python/envs/default/bin/python /Users/yoyo/WorkBuddy/2026-08-03-16-45-23/sports-news-hub/scheduler/run_crawl.py --days 7 >> /Users/yoyo/WorkBuddy/2026-08-03-16-45-23/sports-news-hub/data/crawl.log 2>&1
```

**方式 C · 手动**
界面左侧「🔄 重新抓取」按钮；或命令行 `python scheduler/run_crawl.py --days 7`。

抓取记录（含每次时间/状态/新增条数）写入 `crawl_runs` 表，Web 总览面板会显示「上次抓取」时间，方便确认定时任务在正常运行。日志见 `data/crawl.log`。

## Web 常驻守护进程（关终端 / 重启 Mac 都不掉）

项目附带两个 launchd 配置（均已生成在 `~/Library/LaunchAgents/`）：

| plist | 作用 | 关键配置 |
|-------|------|----------|
| `com.sportsnews.hub.web.plist` | Web 常驻 | `KeepAlive` 崩溃自动重启 + `RunAtLoad` 开机自启，监听 `127.0.0.1:8501`，日志 `data/web.log` |
| `com.sportsnews.hub.plist` | 每日 03:00 抓取 | `StartCalendarInterval` Hour=3，加载即立即跑一次 |

**在你自己的 Terminal.app 里执行（一次性注册，之后全自动）：**
```bash
# 先清掉可能存在的临时进程，避免和 launchd 抢 8501 端口
pkill -f "streamlit run app.py" 2>/dev/null; sleep 1
# 注册两个守护进程（gui/$(id -u) 即当前用户的 GUI 会话域）
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.sportsnews.hub.web.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.sportsnews.hub.plist
# 确认已注册
launchctl list | grep com.sportsnews.hub
# 浏览器打开 http://localhost:8501
```
> 若系统较老不支持 `bootstrap`，改用经典命令：`launchctl load ~/Library/LaunchAgents/com.sportsnews.hub.web.plist` 与 `launchctl load ~/Library/LaunchAgents/com.sportsnews.hub.plist`。
> 卸载（停止常驻）：`launchctl bootout gui/$(id -u)/com.sportsnews.hub.web` 与 `.../com.sportsnews.hub`（或 `launchctl unload` 对应 plist）。

**环境限制（重要）**：在 WorkBuddy 的 Bash 工具沙箱里，`launchctl bootstrap` 会返回 `Input/output error (5)`、`osascript` 控制 Terminal 会被拒绝（权限违例），且后台进程在工具调用结束后会被整体回收——因此**守护进程无法由 AI 在工具内代为注册**，必须由你在真实 Terminal 会话里跑上面那两行。plist 文件本身已校验无误（`plutil -lint` OK），注册即用。

**快速临时常驻（仅会话级，关终端不掉但重启会掉）**：在自己 Terminal 里 `nohup bash scheduler/run_web.sh &` 即可，适合先试用。

## 合规说明
仅聚合公开新闻、控制抓取频率、遵守 robots；公众号/抖音/视频号等需登录或企业密钥，默认未开启（Tier 3）。评论抓取为 best-effort，失败不影响主流程。

## 站点覆盖状态（实测）
| 来源 | 类型 | 近7天可用性 | 说明 |
|------|------|------------|------|
| 新浪体育 | JSON | ✅ 稳定 | 主力源，条目最多 |
| 网易体育 | JSON | ✅ 稳定 | 已修复 docid 拼接 URL |
| 新华网体育 | HTML | ✅ 稳定 | 条目新鲜 |
| 虎扑 | HTML | ✅ 稳定 | 已修正链接 pattern（bbs 帖子） |
| 直播吧 | HTML | ✅ 稳定 | 抓 news.zhibo8.com 子栏目 |
| 搜狐体育 | HTML(best-effort) | ⚠️ 全站流 | 专属接口失效，抓全站再由关键词筛体育 |
| ESPN | RSS | ✅ 稳定 | 英文 |
| BBC Sport | RSS | ✅ 稳定 | 英文 |
| The Guardian | RSS | ✅ 稳定 | 英文 |
| 人民网体育 | RSS | ⚠️ 停更 | 公开 RSS 停留在 2025 年，7天窗口通常无新条目 |
| 央视体育 | RSS | ⚠️ 停更 | 公开 RSS 停留在 2007 年，7天窗口通常无新条目 |
| 腾讯体育 | HTML | ❌ 暂关闭 | 纯 SPA，无稳定新闻接口，留待后续接入 |
| 微博体育 | weibo | ⚠️ best-effort | 按运动搜索 UGC + 热评。需新浪访客 cookie 握手；部分网络/IP 会被 SSO 拦截（返回空），本机正常 IP 通常可用 |
| 百度贴吧 | tieba | ⚠️ best-effort | 按运动抓各「吧」帖子 + 楼层回复。PC 列表页反爬，本机正常 IP 通常可用 |
| 小红书 | html | ❌ 暂关闭(Tier3) | 需 x-s/x-t 签名或登录态，无公开接口 |
| 视频号 | html | ❌ 暂关闭(Tier3) | 无公开 Web 接口，需微信登录态 |
| 抖音 | html | ❌ 暂关闭(Tier3) | 需签名(a_bogus)或登录态，无公开接口 |
| 公众号(搜狗微信) | selenium | ❌ 暂关闭(Tier3) | 需验证码识别，易失效，实验性 |

> **社交平台说明**：微博/贴吧的适配器按标准接口契约实现，并做了访客 cookie 握手 / BAIDUID 种子等反爬处理；在数据中心/受限网络（如本开发沙箱）会被 SSO 或 403 拦截返回空，但在用户本机（正常 residential IP）一般可正常抓取。若微博首次运行返回空，多为访客 cookie 未通过，可在 `sources.yaml` 的 `weibo_sports` 下补充自有 cookie（见下方「接入自有 Cookie」）。

> 央视/人民网为权威源，但其公开 RSS 已停更；如需 7 天内内容，后续可改抓官网栏目页（已列入 TODO）。

---

## v2 功能总览（本轮新增）

### 1. 数据可视化（仪表盘）
- 📈 **各运动日发布量堆叠柱状图**：篮球/足球/电竞等每天发文量对比
- 🔥 **近 7 天新闻热度折线图**：每日体育资讯总量走势
- 🥧 **来源发文占比饼图** + **💗 情感倾向分布饼图**（原生 SVG，无字体依赖）
- ☁️ **热门关键词词云**：基于 jieba 智能提取，字号随词频变化

### 2. 智能文本处理（NLP，本地库优雅降级）
- 📝 **新闻摘要自动生成**（SnowNLP 抽取式）
- 💗 **情感分析**：正面 / 负面 / 中性（球员转会、赛事战报情绪），卡片带彩色徽章
- 🔑 **关键词提取**：每篇文章自动提取名词关键词，可一键按球队/球员聚合筛选

### 3. 个性化交互（存浏览器 localStorage，云端也持久）
- ⭐ **收藏新闻** / 🕘 **浏览历史**
- ⭐ **自定义订阅**：勾选喜欢的运动、球队，一键设为默认筛选
- 🔔 **关键词监控**：输入球队名，自动提醒新相关新闻（带「标记为已读」）

### 4. 实用拓展
- 📝 **Markdown 一键导出** + 原有 Excel/CSV/PDF（含评论）
- 🌐 **外文新闻一键中文翻译**（deep-translator，沙箱降级，云端可用）
- 🖼️ **卡片式图文**：抓配套赛事图（og:image / RSS media），无图时萌系运动 emoji 占位

### 5. 架构升级
- ⏰ 定时自动爬取（GitHub Actions 每日 03:00，云端运行，关电脑也在）
- 🗄️ SQLite 存储历史新闻（FTS5 全文索引，避免重复抓取）
- 🛠️ **爬虫状态面板**：抓取耗时、成功/失败次数、每次来源明细

> 部署：代码已推送至 `github.com/pm5mprzr75-a11y/sports-news-hub`，在 share.streamlit.io 用 GitHub 登录部署即得公网网址（手机可开）。重部署后首次加载会自动 `init_db()` 迁移并跑每日抓取。
