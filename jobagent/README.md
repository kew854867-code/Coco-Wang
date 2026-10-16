# jobagent 交接说明（Handoff）

个人求职投递 agent：发现岗位 → 按 JD 定制简历/Cover Letter → Playwright 自动填表投递 → 结果写回共享 Google Sheet。
**本文不含个人隐私数据**；个人事实在 `profile/facts.json`、完整答题库在 `output/AGENT_PLAYBOOK.md`（二者均被 gitignore，勿提交、勿公开）。

## 1. 目录与关键文件
| 路径 | 作用 |
|---|---|
| `discover.py` / `companies.py` | 扫描公司招聘板（Greenhouse 等 API）→ 写入 `data/jobs.db` |
| `db.py` | SQLite（`jobs` 表；status: pending / materials_ready / submitted / needs_manual / failed / skipped / excluded / expired；tier: priority / skip） |
| `customize.py` / `materials.py` | 生成 1 页定制简历 PDF + Cover Letter PDF；读取 `profile/tailored/<job id>.json`（按 JD 重排 bullet/工具/摘要，只用 facts.json 里的真实事实）；`materials.verify` 校验 1 页 |
| `apply.py` | 核心：Playwright 填表并提交（Greenhouse 为主）。`--submit --limit N [--company X] [--retry]` |
| `report.py` | 汇总报表 |
| `profile/facts.json` | 个人事实唯一来源（gitignored） |
| `profile/learned.json` | 已学会的表单问答，apply.py 自动复用 |
| `profile/claimed_by_other.json` | `[公司, 职位关键词]` 列表：别的 agent 已认领/要排除的岗位 |
| `profile/tailored/*.json` | 每岗位定制覆盖（fit, reason, summary, bullet_order, tools_order, cover） |
| `output/AGENT_PLAYBOOK.md` | 规则 + 答题库 + 踩坑记录（**新 agent 先读它**） |
| `output/run_*.log` | 每次运行日志 |

## 2. 共享 Google Sheet
- Sheet ID：`1ug3Jw5_aQ8V8xfBOJWcsA1eN-5fkRsQLjHu3iPI5MEQ`，tab `Applications`。
- 列：A Company｜B Role｜C Location｜D Applied by｜E Status｜F Applied（**太平洋时间，精确到秒**，如 `2026-10-14 10:03:33`）｜H Apply URL。
- 多 agent 共用：Claude（本 agent）、Muse（点 Ashby/Lever 等人机验证岗位）、Codex、Research（公司线索）。**不要改别人的行**；底部有自动统计表。
- 规则：**先认领（Applied by=Claude）再投递，投完立刻回写**；Ashby/Lever/验证码岗位以 `Applied by=Muse`、`Needs a click - assigned to Muse (…)` 写入；不合格岗位不写入 Sheet；批量改表用一次 batch 调用。
- 时间：DB 的 `applied_at` 是 UTC；太平洋时间 = UTC−7（PDT，11 月初起 −8）。

## 3. 标准流程
1. 读 Sheet 找新增行（Applied by 空/Research/“To apply”）；公司线索 → 找到具体在招岗位。
2. 按筛选标准判断（见 §4），合格者在 Sheet 认领。
3. 写 `profile/tailored/<id>.json` → `materials.py` 生成 PDF。
4. **严格串行**跑 `apply.py --submit`（并行会让 Greenhouse 安全码失效）。
5. 文件握手（后台跑 apply.py，轮询）：
   - `output/question.json`（脚本答不了的题）→ 把答案写入 `output/answer.txt`，并写进 `profile/learned.json`；
   - `output/pending_code.txt`（Greenhouse 发 8 位安全码）→ 在 Gmail 找最新 `Security code for your application to <Company>` 邮件，把码写入 `output/code.txt`。
6. 以页面成功文案或 Gmail 确认邮件为准才算 Submitted；回写 Sheet（E=Submitted，F=太平洋时间）。
7. 小心：不要 `pkill -f apply.py`（会杀自己的 shell），用 `pgrep -f "[a]pply.py"`。

## 4. 投递标准（用户已放宽）
- **投**：活动/合作/BD/社区/市场/项目管理/chief-of-staff/初级 PM/设计/网页开发/视频剪辑；最高到 Manager / Senior Manager / Lead（约 5 年经验）；Head/Director 仅当要求 ≤~8 年。
- **不投并从 Sheet 删除**：不提供 sponsorship、要求公民/绿卡/安全许可、非美国、需到外地坐班、技术型 AV/广播、公共卫生；薪资低于 $100K 下限；Anthropic 已被限投（收到 “Follow-Up” 邮件），不要再投。
- 身份：F-1 OPT，需要 H-1B sponsorship，中国公民。经验最多说 ~5 年，不得编造。
- **推理而非提问**：能从真实经历推断的题（管理经验、团队、AI 基础设施等）直接答；只有法律/敏感题（犯罪记录、政府关系）或 facts 中完全没有的事实才问用户。
- 绝不：编造经历、绕过验证码/反机器人、声称没做过的动作。

## 5. 各招聘板的现实
- **Greenhouse**（含 job-boards、`.eu.greenhouse.io`、embed）：可自动化；URL 规则见 apply.py。
- **Ashby / Lever / Cloudflare / hCaptcha**：自动提交会被拦 → 交 Muse 人工点。
- **Workday / LinkedIn / Wellfound**：需登录账号，agent 做不了。
- Dropbox（Cloudflare）、Intercom（安全码邮件不到）：仅人工。

## 6. 自动化
- 每小时触发（trigger `trig_01J3QGNfuFC1Xj3bkdMfdnXr`）：查 Sheet 有无新增行，有则投；没有就静默。
- 每天早 9 点（太平洋）一轮：用 WebSearch + ATS API 全网找新岗位再筛。

## 7. 当前状态（截至 2026-10-16）
- Claude 累计成功约 143+（见 Sheet 统计表）。9am 轮 11 个已处理：Abnormal、Coinbase、Mercury、Adyen、Greenhouse(PMM Partnerships)、Mixpanel、PagerDuty、Braze、Okta 已提交；
- **待修**：
  - Airbnb（Senior Manager, Technical Brand & Content）卡在 `Location (City)` 自动补全字段；
  - Natera（Sr. Speaker Programs Manager）要求填雇佣经历 “Company name”；
  - Okta（Lead Creative Operations Manager）已提交但未收到确认邮件（Sheet 状态为 pending confirmation）。
- **待办**：约 80 条公司线索（“Research” 行，如 Pulumi、HashiCorp、Statsig、PostHog、HubSpot、Reframe Systems 等）还没找具体岗位；Wellfound 线索（Firecrawl、aperture labs 等）需要登录或人工邮件，agent 做不了。
- 其他 agent 的行（Muse/Codex）不要动；Menlo Research 标注 DO NOT APPLY。

## 8. 安全与合规
- `profile/`、`data/`、`output/` 均 gitignore，含个人信息，**不要提交或外发**。
- 提交/推送只在用户要求时做；分支 `claude/work-status-check-fxdvc0`，草稿 PR #2。
