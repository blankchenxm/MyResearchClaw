# DNL 精读笔记 — 平台时序代码生成

## 0) Metadata
- **Title:** Platform-Specific Code Generation from Platform-Independent Timed Models
- **Alias:** 平台时序代码生成
- **Authors / Org:** BaekGyu Kim, Lu Feng, Oleg Sokolsky, Insup Lee | University of Pennsylvania
- **Venue / Status:** RTSS (2015)
- **Links:**
  - Paper: https://dblp.org/rec/conf/rtss/KimFSL15
  - PDF: https://repository.upenn.edu/bitstreams/9c9bd30e-6c44-4003-ba46-1e8663a2d1c2/download
  - Repository: https://repository.upenn.edu/entities/publication/daef275d-8ad3-4602-b1fd-3b2cb3c690bc
- **Tags:** code-generation, timed-models, ILP, embedded-software, real-time-systems, medical-device
- **My rating:** 4/5

## 1) 一句话 Why-read
这篇论文解决的是一个很工程化、但很难被“纯建模”自动化掉的问题：如果平台本身会引入 I/O 和通信延迟，那么仅按平台无关的定时模型生成代码，往往会把形式化验证过的时序假设打坏。作者给出的是一个可操作的补偿策略：把平台延迟显式折进模型，再用 ILP 调整时序参数，尽量让生成代码在真实平台上仍满足 delay bound。

## 2) CRGP 拆解 Introduction

### C - Context
文中从安全关键实时嵌入式系统切入，问题不是“代码能不能跑”，而是“输入到输出之间的延迟上界能不能守住”。这类约束在医疗设备、控制系统里非常典型，例如传感器触发后，执行器必须在有限时间内响应。

### R - Related work
作者对准的是传统模型驱动开发流程：先验证平台无关模型，再用 code generator 直接出代码。这个流程默认平台对 I/O 的处理几乎是“无限快”的，但现实中 I/O driver、调度和通信抖动都会把时序拉歪。作者还提到他们之前做过把平台架构因素建模、再生成测试的工作，但那一类方法仍不足以保证“生成出来的代码”在真实平台上保留已验证的时序性质。

### G - Gap
核心缺口是：系统模型里的 timed behavior 和平台上的 code-level timed behavior 不是同一个东西。把平台延迟加进模型并不自动等价于可部署代码，因为生成后再落到平台时，平台延迟会再次叠加，导致形式化证明和实际执行脱节。

### P - Proposal
作者的提案是两步式模型变换：
1. 把平台处理延迟显式建模，形成 software model，而不是继续把平台当成“零延迟黑箱”。
2. 用 Integer Linear Programming 调整 timing parameters，目标是补偿平台处理延迟，同时尽量保持和原系统模型的时序偏移最小。

从可见文字看，ILP 约束会同时刻画：
- 模型中沿路径累积的 I/O delay
- 平台处理延迟
- 系统模型与实现之间的 delay-bound 差异

这意味着作者不是只“平移一个常数”，而是在路径级别做约束求解。

## 3) Figures
当前能稳定访问到的公开文本里，图像本身没有完整抽取出来，但论文的结构已经能从文字里确认出几个关键图示主题：
- 问题动机图：平台无关模型直接生成代码后，平台延迟会破坏时序保证。
- 变换流程图：system model -> software model -> generated code。
- 评估图/表：infusion pump case study 下，比较原始生成与补偿后生成在时序保持上的差异。

如果要补全这一节，最值得回到 PDF 原文核对的是“模型变换流程”和“实验结果图表”的具体坐标与数值。

## 4) Experiments
公开可见的摘要和页面文本都指向一个 infusion pump 的 case study。实验结论是：用作者方法生成的代码，在 preserving timing constraints 这件事上明显更好。

我能可靠确认的实验信息是：
- 场景是 infusion pump systems
- 指标关注的是 timing constraints preservation
- 结果方向是 transformed software model 生成的代码优于直接从平台无关模型生成的版本

我不能从当前可访问文本里稳定恢复的，是具体基准平台、测试用例数量、ILP 求解规模和数值提升幅度。这个限制要如实保留。

## 5) Why it matters
这篇工作的价值不在于某个很花哨的新模型，而在于它把“平台差异”从后验验证问题前移成了生成时的优化问题。对医疗和其他 safety-critical 设备来说，这种思路很重要，因为它允许你在生成阶段就把平台迟滞当成设计变量，而不是等代码落地后再补救。

从今天的嵌入式实践看，这个框架也很像一条可复用的路线：
- 先把平台契约形式化
- 再把 timing 参数当成可求解变量
- 最后让生成代码尽量继承模型层的时序保证

## 6) Next steps
- 把 PDF 原文的算法部分补读出来，确认 ILP 的变量、目标函数和可行性判定条件。
- 对照 2019 年的后续版本 `Determining Timing Parameters for the Code Generation from Platform-Independent Timed Models`，看这篇 RTSS 版本在哪些地方是更早、更粗的原型。
- 如果后续要把这条思路迁移到 MCU 固件生成，最先要验证的是 I/O 延迟建模是否能覆盖目标平台的中断、DMA 和驱动栈。

## 7) Scoring
评分拆分如下：
- Base = 1
- Quality bonus = 1，因为它把平台延迟补偿形式化成了可求解的 ILP，方法路径清楚，工程可落地
- Observation bonus = 2，因为它抓住了“平台无关模型 -> 平台特定代码”这条链路里最容易被忽略、但最致命的时序偏差

总分 = 1 + 1 + 2 = **4/5**

## 8) 备注
当前可访问来源足够支撑摘要、方法主线和案例方向，但无法稳定抽出整篇 PDF 的全部图表和定理细节。因此这份笔记更偏“可验证的深读摘要”，不是逐页复刻。
