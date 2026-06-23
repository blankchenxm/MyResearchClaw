# Academic Platform API Cookbook

各学术平台 API 调用速查。所有示例可直接复制执行。

平台覆盖：arXiv、Semantic Scholar、DBLP、OpenAlex、Unpaywall、Google Scholar (CDP)。

---

## arXiv

**根 URL**：`https://export.arxiv.org/api/query`
**鉴权**：无需
**格式**：Atom XML
**速率**：建议 3s/请求

### 搜索

```bash
curl -s "https://export.arxiv.org/api/query?search_query=ti:silent+speech&max_results=10&sortBy=submittedDate&sortOrder=descending"

curl -s "https://export.arxiv.org/api/query?search_query=ti:transformer+AND+cat:cs.LG&max_results=10"
```

**search_query 字段前缀**：

| 前缀 | 说明 |
|---|---|
| `ti:` | 标题 |
| `au:` | 作者（`LastName_FirstInitial`） |
| `abs:` | 摘要 |
| `cat:` | 分类（`cs.AI` / `cs.LG` / `eess.AS` 等） |
| `all:` | 全字段 |

### PDF 直链

```
https://arxiv.org/pdf/{arxiv_id}
```

不依赖任何字段判断，直接构造即可。arXiv 上的论文 100% 有 PDF。

### 响应字段映射

| XML 路径 | 标准字段 |
|---|---|
| `<title>` | title |
| `<author><name>` | authors[] |
| `<summary>` | abstract |
| `<published>` 前 4 位 | year |
| `<arxiv:doi>` | doi |
| `<id>` 末段 | arxiv_id |

---

## Semantic Scholar

**根 URL**：`https://api.semanticscholar.org/graph/v1`
**鉴权**：Header `x-api-key: YOUR_KEY`（强烈建议；无 Key 时 100 req/5min 必触发 429）
**格式**：JSON

### 推荐 fields 组合

```
title,authors,year,abstract,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue,publicationTypes
```

### 搜索

```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/search?query=silent+speech+EMG&fields=title,authors,year,abstract,citationCount,influentialCitationCount,externalIds,openAccessPdf&limit=10" \
  -H "x-api-key: YOUR_KEY"
```

### 精确查询（DOI / arXiv ID）

```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/DOI:10.1145/3290605.3300376?fields=title,authors,year,citationCount,openAccessPdf,externalIds" \
  -H "x-api-key: YOUR_KEY"

curl -s "https://api.semanticscholar.org/graph/v1/paper/ARXIV:1807.06677?fields=title,authors,year,citationCount,openAccessPdf,externalIds" \
  -H "x-api-key: YOUR_KEY"
```

### 批量查询（最多 500 篇）

```bash
curl -s -X POST "https://api.semanticscholar.org/graph/v1/paper/batch?fields=title,year,citationCount,openAccessPdf,externalIds" \
  -H "Content-Type: application/json" \
  -d '{"ids":["DOI:10.xxx/xxx","ARXIV:2301.00001"]}' \
  -H "x-api-key: YOUR_KEY"
```

### 引用 / 被引

```bash
curl -s "https://api.semanticscholar.org/graph/v1/paper/{paper_id}/references?fields=title,year,authors,citationCount,influentialCitationCount&limit=50" \
  -H "x-api-key: YOUR_KEY"

curl -s "https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations?fields=title,year,authors,citationCount&limit=50" \
  -H "x-api-key: YOUR_KEY"
```

### 响应字段映射

| JSON 字段 | 标准字段 |
|---|---|
| `title` | title |
| `authors[].name` | authors[] |
| `year` | year |
| `abstract` | abstract |
| `citationCount` | citations |
| `influentialCitationCount` | influential_citations |
| `externalIds.DOI` | doi |
| `externalIds.ArXiv` | arxiv_id（**A 大写**） |
| `openAccessPdf.url` | pdf_url |
| `venue` | venue |

**陷阱见**：`references/site-patterns/semanticscholar.org.md`

---

## DBLP

**根 URL**：`https://dblp.org`
**鉴权**：无需
**格式**：JSON / HTML
**适用**：venue listing 完整性核对，比 S2 的 venue 字段权威

### Venue 列表页（按年份）

URL 规律：
```
https://dblp.org/db/conf/{venue}/{venue}{year}.html
```

示例：
- SenSys 2024：`https://dblp.org/db/conf/sensys/sensys2024.html`
- IMWUT 2024（期刊）：`https://dblp.org/db/journals/imwut/imwut8.html`

### 搜索 API

```bash
curl -s "https://dblp.org/search/publ/api?q=silent+speech+venue:SenSys&format=json&h=30"
```

参数：
- `q`：搜索词（支持 `venue:` `year:` 等过滤）
- `format`：`json` / `xml`
- `h`：返回数（最大 1000）

### 响应字段映射（JSON）

| JSON 路径 | 标准字段 |
|---|---|
| `result.hits.hit[].info.title` | title |
| `result.hits.hit[].info.authors.author[].text` | authors[] |
| `result.hits.hit[].info.venue` | venue |
| `result.hits.hit[].info.year` | year |
| `result.hits.hit[].info.doi` | doi |
| `result.hits.hit[].info.ee` | url（可能是 DOI 或 PDF） |

---

## OpenAlex

**根 URL**：`https://api.openalex.org`
**鉴权**：无需；建议带 `mailto` 参数
**格式**：JSON
**适用**：跨学科开放获取状态、引用关系

### 按 DOI 查询 OA

```bash
curl -s "https://api.openalex.org/works?filter=doi:10.1145/3290605.3300376&select=id,open_access,best_oa_location&mailto=YOUR_EMAIL"
```

### 关键字搜索

```bash
curl -s "https://api.openalex.org/works?search=silent+speech&per-page=10&mailto=YOUR_EMAIL"
```

### 响应字段映射

| JSON 字段 | 标准字段 |
|---|---|
| `title` | title |
| `authorships[].author.display_name` | authors[] |
| `publication_year` | year |
| `primary_location.source.display_name` | venue |
| `doi` | doi |
| `cited_by_count` | citations |
| `open_access.oa_status` | open_access_status |
| `best_oa_location.pdf_url` | pdf_url |

---

## Unpaywall

**根 URL**：`https://api.unpaywall.org/v2`
**鉴权**：必须带 email 参数
**格式**：JSON
**适用**：合法 OA PDF 链接、出版商访问限制判定

```bash
curl -s "https://api.unpaywall.org/v2/10.1145/3290605.3300376?email=YOUR_EMAIL"
```

### 响应字段映射

| JSON 字段 | 标准字段 |
|---|---|
| `doi` | doi |
| `title` | title |
| `is_oa` | open_access_boolean |
| `oa_status` | open_access_status (`gold`/`green`/`hybrid`/`bronze`/`closed`) |
| `best_oa_location.url_for_pdf` | pdf_url |
| `best_oa_location.license` | license |

### full_text_status 判定

| 条件 | 状态 |
|---|---|
| `url_for_pdf` 存在且响应为 PDF 字节 | `open_pdf` |
| `is_oa=false` | `no_open_pdf` |
| 出版商页面存在但 PDF 需登录 | `needs_institution` |
| URL 返回 HTML | `html_not_pdf` |
| 403 / Cloudflare / 验证码 | `anti_bot_blocked` |

---

## Google Scholar

**官方 API**：无
**唯一可靠方式**：CDP 浏览器自动化（直连用户 Chrome）
**不要尝试**：WebFetch、curl 直接抓 `scholar.google.com`、WebSearch

### CDP 操作流程

```bash
# 1. 确保 CDP Proxy 就绪
bash scripts/check-deps.sh

PORT="${CDP_PROXY_PORT:-3456}"

# 2. 打开 Scholar 搜索页（直接带 q 参数）
QUERY=$(python3 -c "import urllib.parse; print(urllib.parse.quote('silent speech EMG wearable'))")
TARGET=$(curl -s "http://127.0.0.1:${PORT}/new?url=https://scholar.google.com/scholar?q=${QUERY}" \
  | node -p "JSON.parse(require('fs').readFileSync(0,'utf8')).targetId")

# 3. 等待结果加载
sleep 2

# 4. 提取结果（标题 / 链接 / 引用数 / 全文链接）
curl -s -X POST "http://127.0.0.1:${PORT}/eval?target=$TARGET" -d '
JSON.stringify(Array.from(document.querySelectorAll(".gs_ri")).slice(0,10).map(el => ({
  title: el.querySelector(".gs_rt a")?.textContent?.trim(),
  link: el.querySelector(".gs_rt a")?.href,
  authors_venue: el.querySelector(".gs_a")?.textContent?.trim(),
  cited_by: el.querySelector(".gs_fl a")?.textContent?.match(/Cited by (\d+)/)?.[1],
  full_text_links: Array.from(el.parentElement?.querySelectorAll(".gs_or_ggsm a") || []).map(a => a.href)
})))
'

# 5. 关闭 tab
curl -s "http://127.0.0.1:${PORT}/close?target=$TARGET"
```

### 主要用途

- 获取 Scholar 引用数（最全面）
- PDF 级联 Step 5：在前 4 步失败时找作者自存档的 PDF
- 发现其他平台未收录的论文

### 注意

- 操作间隔 ≥3s，避免触发 CAPTCHA
- 多次连续请求后必须 sleep 至少 10s
- 详见 `references/site-patterns/scholar.google.com.md`（如有）

---

## 通用使用规则

1. **优先级**：DBLP（venue 完整性）> Semantic Scholar（元数据 + 引用）> arXiv（最新预印本）> OpenAlex/Unpaywall（OA 状态）> Google Scholar（兜底）
2. **降级**：S2 返回 429 → 立刻切 DBLP，不重试
3. **错误处理**：网络失败重试 1 次后切平台，不要在同一平台死循环
4. **PDF 获取**：永远走 `references/pdf-cascade.md` 5 步，不要在 SKILL.md 里写新的 PDF 获取逻辑
