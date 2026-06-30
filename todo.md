# MyResearchClaw — Queue & Resume Roadmap

## Phase 1: Paper Reader — Per-Stage Resume

**目标**：精读任务在任意阶段失败后，重新触发时从最近的 artifact 继续，而不是从头重读。

已有基础：`_get_pipeline_step_progress()` 已通过 `output/tmp/{paper_id}/` 里的 artifact 文件知道跑到哪步了。  
需要做的是利用这些文件构建 resume prompt，并让失败时保留进度而非重置。

### 1.1 新增 `build_paper_reader_resume_prompt(paper_id, url, title)`
- 文件：`serve.py`
- 逻辑：检测 `output/tmp/{paper_id}/` 里存在哪些 artifact（按 `_get_pipeline_step_progress` 的顺序），找到最后完成的步骤
- 构建 prompt 告知 agent：
  - "以下步骤已完成，对应文件已存在，跳过它们：A, B, C"
  - "从步骤 D 继续"
- Artifact → 步骤映射（已在代码里，直接复用）：
  ```
  _resolve.json   → Step 0: 解析 URL
  _metadata.json  → Step 1: 获取元数据
  _fetch.json     → Step 2: 提取正文
  _source_manifest.json → Step 3: 提取证据
  _evidence.json  → Step 4: 提取图表
  _assets.json    → Step 5: 规划图表
  _figures.json   → Step 6: 提取图表
  _figure_table_decisions.json → Step 7: 图表决策
  _bundle.json    → Step 8: 构建 bundle
  _note.plan.json → Step 9: 写 note_plan
  _note.md        → Step 10: 撰写笔记草稿
  _write.json     → Step 11: 完成（不应到这里还失败）
  ```

### 1.2 修改 `read_paper_bg()`
- 文件：`serve.py`
- 在调用 `build_paper_reader_prompt()` 前，检查 `output/tmp/{paper_id}/` 是否有 artifact
  - 有 → 调用 `build_paper_reader_resume_prompt()` 替代
  - 无 → 照旧用 `build_paper_reader_prompt()`（全新开始）

### 1.3 修改失败后的状态处理
- 文件：`serve.py`
- 当前：失败时调 `restore_paper_state()`（把论文状态回滚到精读前）
- 改为：若 `output/tmp/{paper_id}/` 有 artifact，**保留** 当前 progress（比如 58%），设 `status="error_resumable"` 而非重置
- 若无 artifact（完全没跑起来），才回滚到原状态

### 1.4 UI：手动"继续精读"按钮
- 文件：`skills/conference-scout/assets/kanban.html`
- 当 paper `status == "error_resumable"` 时，将精读按钮变为"▶ 继续精读"（不是"重新精读"）
- 点击逻辑与现有 `triggerRead()` 相同（`read_paper_bg` 内部会自动用 resume prompt）
- **按钮是主要恢复手段，QRunner 只是自动帮用户点这个按钮**
- 按钮文案区分：
  - `error_resumable`（有 artifact）→ "▶ 继续精读（从 XX% 恢复）"
  - `unread` / 完全失败 → "📖 精读论文"（重新开始）

### 1.5 错误类型字段
- 文件：`serve.py`
- 在 paper 的 fields 里加 `read_error_type`：`"rate_limit"` / `"permanent"` / `"pdf_failed"`
- 通过检测 claude CLI 输出里的关键词判断（`rate limit`, `429`, `quota`, `overload`）
- QRunner 只对 `rate_limit` 类型自动重试

---

## Phase 2: Scout — 每轮 Checkpoint

**目标**：不只 Round 3，每一轮完成后都保存状态，中断后从上次完成的轮次继续。

已有基础：Round 3 有 `scout_checkpoint_r3.json`，Round 4 之后 serve.py 已从 checkpoint 读取候选。

### 2.1 SKILL.md — 每轮写 checkpoint
- 文件：`skills/conference-scout/SKILL.md`
- 在 Round 0、1、2、4、5、6 末尾加 checkpoint 写入代码（类似现有 Round 3 的写法）
- Checkpoint 内容按轮次：
  - Round 0: `queries[]`（扩展后的查询词）
  - Round 1: `discovery_papers[]`（发现的论文列表）
  - Round 2: `anchors{}`（完整 anchor JSON，现有 Round 3 checkpoint 已包含）
  - Round 3: 现有 → 保留
  - Round 4: `gate_passed[]`（通过 gate 的论文）
  - Round 5: `expanded_candidates[]`
  - Round 6: `timeline[]`（分类后的时间线）

### 2.2 serve.py — 通用 checkpoint 加载
- 文件：`serve.py`
- 重构 `_load_scout_checkpoint()` → 扫描所有轮次 checkpoint 文件，返回最新的
- 文件命名：`scout_checkpoint_r{N}.json`（已有 r3，扩展到 r0-r6）
- `run_conference_scout_phase1_bg()` 根据 `last_completed_round` 决定从哪轮开始

### 2.3 serve.py — 每轮 resume prompt
- 文件：`serve.py`
- 现有 `build_conference_scout_resume_prompt()` 只处理从 Round 4 开始
- 扩展为：根据 `last_completed_round` 生成不同的 resume prompt
  - 从 Round 1 继续：提供 queries，跳过 Round 0
  - 从 Round 3 继续：现有逻辑
  - 从 Round 5 继续：提供 gate_passed candidates，跳过 Round 0-4
  - 从 Round 7 继续：理论上不需要（Round 7 失败代表写 JSON 失败，重跑）

### 2.4 UI：Scout "继续"按钮文案修正
- 文件：`serve.py`（HTML 部分）
- 现有"↩ 重试"按钮已能触发断点续传（有 checkpoint 时从 Round 4 继续）
- 改进：按钮文案根据 checkpoint 状态动态显示
  - 有 checkpoint → "▶ 从 Round N 继续"（当前已实现 `retryBtn.textContent = ...`，保持）
  - 无 checkpoint → "↩ 从头重试"
- **按钮是主要恢复手段，QRunner 只是自动帮用户点这个按钮**

### 2.5 错误类型字段
- 文件：`serve.py`
- `save_scout_status()` 增加 `error_type` 字段（同 Paper Reader 1.5）
- 通过 claude CLI 输出检测：rate_limit / permanent

---

## Phase 3: 队列系统

### 3.1 Scout 队列
- 文件：新建 `output/scout_queue.json`，格式：
  ```json
  {
    "pending": [
      {"topic": "...", "description": "...", "year_start": 2020, "year_end": 2026,
       "venue_group": "...", "specific_venues": [], "submitted_at": "...", "submitter": "anonymous"}
    ]
  }
  ```
- 文件：`serve.py`
  - 新增 `enqueue_scout(topic, ...)` 函数：把任务写入 pending 列表
  - `/api/start-scout` 改为：若有任务运行中 → 加入队列而非返回 409；若空闲 → 直接运行
  - Scout 完成后（成功或失败）：检查队列，自动启动下一个

### 3.2 Paper Reader 队列
- 文件：新建 `output/reader_queue.json`，格式：
  ```json
  {
    "pending": [
      {"paper_id": "...", "url": "...", "title": "...", "submitted_at": "..."}
    ]
  }
  ```
- 文件：`serve.py`
  - `/api/read-paper`：若有精读正在运行 → 加入队列；若空闲 → 直接运行
  - 精读完成后：检查队列，自动启动下一个

### 3.3 UI — 队列状态显示

**Topic Navigator（serve.py 主页）：**
```
┌─────────────────────────────────────────────┐
│ 🔄 正在调研：Cameras in wearable            │
│    [████████░░] Round 6 · 组装时间线...      │
├─────────────────────────────────────────────┤
│ ⏳ 等待队列（2 个）                          │
│    1. EMG gesture recognition               │
│    2. On-device LLM inference               │
└─────────────────────────────────────────────┘
```
- 文件：`serve.py`，扩展 `render_topic_index_html()` 读取队列文件并渲染

**论文卡片（kanban.html）：**
- 精读按钮状态新增：`"排队中 #2"` （当 paper 在 reader_queue.pending 里）
- 通过轮询 `/api/reader-queue-status` 更新

### 3.4 新增 API 端点（serve.py）
- `GET /api/scout-queue` → 返回 pending 列表
- `GET /api/reader-queue` → 返回 reader pending 列表
- `DELETE /api/scout-queue/{index}` → 取消队列中某个任务（用户可撤回）

---

## Phase 4: QRunner

**目标**：自动检测额度是否恢复，替代人工点"继续"按钮。

### 4.1 新增 `scripts/queue-runner.py`
逻辑：
```
读取 scout_status.json
  若 error_type == "rate_limit":
    调用 POST /api/start-scout（等于点了"重试"按钮）
    等待 10 秒，检查是否成功启动
    若仍失败（又返回 rate_limit）→ 退出，等下次 cron

读取 papers.json 中 status == "error_resumable" 且 read_error_type == "rate_limit" 的论文
  若存在：
    取第一个，调用 POST /api/read-paper
    等待 10 秒确认启动

若 scout_queue.pending 不为空且当前无运行任务：
  调用 /api/start-scout 启动队列头部任务

若 reader_queue.pending 不为空且当前无运行精读：
  调用 /api/read-paper 启动队列头部任务

写日志到 output/logs/queue-runner.log
```

### 4.2 Rate limit 检测（serve.py）
检测 claude CLI 输出中以下关键词，写入 `error_type`：
- `"rate limit"` / `"429"` / `"too many requests"` → `"rate_limit"`
- `"quota"` / `"usage limit"` / `"monthly"` → `"quota_exceeded"`（不自动重试）
- 其他 → `"permanent"`（不自动重试，需人工排查）

### 4.3 Cron 配置
- Mac mini：launchd plist，每 3 分钟运行一次（类似现有 sync-github.sh）
- Linux：crontab，`*/3 * * * *`
- 日志：`output/logs/queue-runner.log`（仅在有操作时写入，不写心跳）

---

## 实现顺序

| 阶段 | 预计改动范围 | 优先级 |
|---|---|---|
| Phase 1.1-1.4 Paper Reader Resume | serve.py + kanban.html | 高 |
| Phase 1.5 错误类型字段 | serve.py | 高（QRunner 依赖） |
| Phase 2.1-2.4 Scout Per-Round | SKILL.md + serve.py | 中 |
| Phase 3.1-3.2 队列后端 | serve.py | 中 |
| Phase 3.3-3.4 队列 UI | serve.py + kanban.html | 中 |
| Phase 4 QRunner | scripts/ + serve.py | 中（依赖 1.5） |

---

## 不做的事（范围外）

- Paper Reader 的 per-step token usage tracking（意义不大）
- 多并发 Scout（设计上保持串行）
- 用户身份认证（当前共享同一个账号）
- 每周额度耗尽的自动处理（人工知悉即可）
