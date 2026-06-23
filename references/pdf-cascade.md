# PDF Acquisition Cascade

所有 skill 统一使用此 5 步级联逻辑获取论文 PDF。每一步失败才进下一步；任何一步成功就停止并写入 `full_text_status = open_pdf`。

---

## Cascade Steps

### Step 1 — arXiv 直链

**条件**：论文有 arXiv ID（来自 S2 `externalIds.ArXiv`、用户输入、或 `output/papers.json` 中已记录的 `arxiv_id`）

**操作**：
```
GET https://arxiv.org/pdf/{arxiv_id}
```

**注意**：不依赖 S2 `openAccessPdf` 字段（经常为 null，但 PDF 实际可得）。直接构造 URL 即可。

---

### Step 2 — S2 openAccessPdf

**条件**：S2 API 响应中 `openAccessPdf.url` 不为 null

**操作**：使用 `openAccessPdf.url`

**调用模板见**：`references/api-cookbook.md` Semantic Scholar 一节

---

### Step 3 — OpenAlex OA 检查（有 DOI 时必须执行）

**条件**：论文有 DOI

**操作**：
```
GET https://api.openalex.org/works?filter=doi:{doi}&select=id,open_access,best_oa_location&mailto=...
```

**提取**：`results[0].best_oa_location.pdf_url`；为 null 则进 Step 4

---

### Step 4 — Unpaywall（有 DOI 时必须执行）

**条件**：论文有 DOI 且 Step 3 失败

**操作**：
```
GET https://api.unpaywall.org/v2/{doi}?email=...
```

**提取**：`best_oa_location.url_for_pdf`；`is_oa=false` 则进 Step 5

---

### Step 5 — Google Scholar（CDP）

**条件**：前 4 步均失败，且 CDP Proxy 已就绪（`bash scripts/check-deps.sh`）

**操作**：
1. 用 CDP 打开 Google Scholar，搜索论文标题（`scholar.google.com/scholar?q={title}`）
2. 提取首个匹配结果的所有外链（DOM `.gs_or_ggsm a`）
3. 优先取 `.pdf` 直链；其次取出版商/作者主页的全文链接

**调用模板见**：`references/api-cookbook.md` Google Scholar 一节

**注意**：操作间隔 ≥3s 避免触发 CAPTCHA。详见 `references/site-patterns/scholar.google.com.md`（如有）。

---

### Step 6 — 停止并报告

5 步全部失败 → 记录 `full_text_status`，不再尝试，向上游 fail closed。

---

## full_text_status 枚举

写入 `output/papers.json` 中该论文的字段：

| 值 | 含义 |
|---|---|
| `open_pdf` | 找到可公开访问 PDF，已下载 |
| `needs_institution` | 出版商页面存在 PDF 但需要订阅/机构权限 |
| `no_open_pdf` | Unpaywall `is_oa=false`，无合法开放全文 |
| `anti_bot_blocked` | 被 Cloudflare / CAPTCHA / 403 拦截 |
| `html_not_pdf` | PDF 路由返回 HTML 页面（非 PDF 字节） |
| `unknown` | 证据不足，未完整跑完级联 |

判别提示：
- 下载后用 `b"%PDF-" in data[:1024]` 验证字节是否为真 PDF
- 收到 HTML 时 → `html_not_pdf`
- 收到 403 / 验证码页 → `anti_bot_blocked`
- DOI 存在但 Unpaywall `is_oa=false` 且无 OA 镜像 → `needs_institution` 或 `no_open_pdf`

---

## 快速预检模式（conference-scout Round 4.5 用）

某些场景只需快速判断"是否有开放 PDF"，不需要真的下载（如候选确认表中的 PDF 列）：

只执行 **Step 1 + Step 2**：
- arXiv ID 存在 → 标记 ✓ arXiv
- S2 `openAccessPdf` 非 null → 标记 ✓ S2
- 否则 → 标记 ✗（不进 Step 3-5，避免阻塞）

完整级联留到 paper-reader 真正精读时再执行。

---

## 落盘规范

PDF 保存路径：`output/pdfs/{topic_slug}/{paper_id}.pdf`

写入 `papers.json` 的字段：
```json
"full_text_status": "open_pdf",
"pdf_url": "https://arxiv.org/pdf/2401.12345",
"open_access_status": "green"
```

- `pdf_url`：实际命中的 URL（不是构造前的候选）
- `open_access_status`：`gold` / `green` / `hybrid` / `closed` / `unknown`，来自 OpenAlex 或 Unpaywall
