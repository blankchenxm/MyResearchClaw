---
domain: semanticscholar.org
aliases: [Semantic Scholar, S2]
updated: 2026-06-19
---

## 平台特征

- AI2 维护的学术搜索引擎，覆盖 2 亿+ 论文
- 完整公开 REST API，JSON 格式
- 无 Key 可用但速率受限；免费 Key 可显著提升速率
- 引用数据完整，支持引用/被引查询
- 支持多种 ID 互查：DOI、arXiv ID、ACM ID、MAG ID、CorpusId

## API Key

- 免费申请：https://www.semanticscholar.org/product/api#api-key-form
- 使用方式：请求头加 `x-api-key: {your_key}`
- 强烈建议获取：无 Key 时单 session 多次调用必触发 429

## 推荐 fields 组合

```
title,authors,year,abstract,citationCount,influentialCitationCount,externalIds,openAccessPdf,venue,publicationTypes
```

`fields` 参数**必须显式指定**，默认只返回 `paperId` 和 `title`。

## paperId 格式

| 格式 | 示例 |
|---|---|
| S2 内部 ID | `649def34f8be52c8b66281af98ae884c09aef38a` |
| DOI | `DOI:10.18653/v1/P16-1162` |
| arXiv ID | `ARXIV:1706.03762` |
| ACM | `ACM:3295222.3295349` |
| MAG | `MAG:112218234` |
| CorpusId | `CorpusId:13756489` |

## 已知陷阱

- **大小写敏感**：`externalIds.ArXiv` 中 A 大写；代码中字段名错了字段为空
- **openAccessPdf 误判**：`openAccessPdf` 为 null **不代表无 PDF**，仅代表 S2 未收录该 PDF。此时必须走 `references/pdf-cascade.md` Step 1（arXiv 直链）/ Step 3-4（OpenAlex / Unpaywall）补充
- **批量上限**：`/paper/batch` 单次最多 500 篇，超出需分批
- **429 处理**：单 session 调用 ~100 次后必触发；触发后**立刻切 DBLP**，不要重试同一端点
- **abstract 为 null**：某些非英文论文的 `abstract` 字段为 null，即使论文实际有摘要
- **venue 字段不可靠**：S2 的 `venue` 字符串是自动填的，权威性低；要确认某篇是不是 SenSys 2024，**用 DBLP** 的 venue listing 核对，不要只看 S2 的 venue 字段
- **authors 字段瘦**：默认只返回 `authorId` 和 `name`，不含机构；需机构信息得单独查 author 端点

## 检索调用模板

完整 curl 示例见 `references/api-cookbook.md` Semantic Scholar 一节。
