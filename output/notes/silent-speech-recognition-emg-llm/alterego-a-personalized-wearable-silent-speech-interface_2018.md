# DNL 精读笔记 — AlterEgo 静默语音接口

## 0) Metadata
- **Title:** AlterEgo: A Personalized Wearable Silent Speech Interface
- **Alias:** AlterEgo 静默语音接口
- **Authors / Org:** Arnav Kapur, Shreyas Kapur, Pattie Maes | MIT Media Lab
- **Venue / Status:** IUI 2018
- **Links:**
  - **Paper:** https://dam-prod.media.mit.edu/x/2018/03/23/p43-kapur_BRjFwE6.pdf
  - **PDF:** https://dam-prod.media.mit.edu/x/2018/03/23/p43-kapur_BRjFwE6.pdf
  - **Local PDF:** `output/pdfs/silent-speech-recognition-emg-llm/alterego-a-personalized-wearable-silent-speech-interface_2018.pdf`
- **Tags:** silent speech, wearable, EMG, neuromuscular, bone conduction, HCI
- **My rating:** 4/5

## 1) 一句话 Why-read
这篇论文几乎是“无声语音接口”路线的经典系统原型：它不是做纯粹的离线识别，而是把非侵入式神经肌肉信号采集、个性化识别、以及骨传导私密反馈连成一个闭环可穿戴设备，因此非常适合作为后续 EMG + LLM silent speech 系统的历史基线和工程参照。

## 2) CRGP: Context, Related work, Gap, Proposal

### Context
作者想解决的问题很明确：让用户在不出声、几乎不做可见口型的情况下，仍然能用自然语言和计算设备、AI 助手或其他人交流。这个目标同时触及三个关键词：隐私、可穿戴、以及“像对自己说话一样”的自然交互。

### Related work
论文先把相关路线拆成两类：
- **侵入式**：如脑植入、口腔内传感器、磁珠定位、超声加视频等。这些方法要么侵入性强，要么硬件笨重，不容易走向日常使用。
- **非侵入式**：如 EEG、视频唇读、非可听低语、surface EMG 等。问题通常在于信噪比、对显性口型的依赖、或对特定发音动作的强约束。

作者特别强调，已有 EMG 方案常常仍需要用户明显地“做嘴型”或刻意发音，而 AlterEgo 试图捕捉的是更接近内在发音的神经肌肉活动。

### Gap
缺口不是“能不能识别少量词”，而是更工程化的三个缺口：
- 能否做到**非侵入**、**可穿戴**、且用户不必明显动嘴。
- 能否把识别结果变成一个**闭环接口**，而不是单纯分类器。
- 能否在可接受的准确率和延迟下，支撑真正的应用场景，而不是只在实验室里做演示。

### Proposal
作者的方案是一个完整系统，而不是单点模型：
- 用头带/面罩式可穿戴结构，在面部和颈部选定 7 个皮肤区域采集 neuromuscular 信号。
- 用 250 Hz 采样、24x 增益、带通 + 陷波 + ICA 等流程清洗信号。
- 将信号转成类似 speech 特征的表示，再用 1D CNN 做词级分类。
- 用骨传导耳机把结果反馈给用户，构成“silent input + private output”的双向接口。

从设计哲学看，这篇论文的核心不是“把 EMG 当作另类麦克风”，而是把它当作一种私密的人机通道，并试图把 AI、提醒、计算、通讯这些功能都叠在这个通道上。

## 3) Figures

### Figure 1
系统愿景图：AlterEgo 把机器交互塑造成“像和自己对话”。这张图定义了论文的叙事中心，不是替代语音，而是把语音变成内隐、私密、无外显动作的交互。

### Figure 2
电极位置筛选结果图。作者先在 30 个点位上做探索，再筛到 7 个 target area，说明这不是拍脑袋选位置，而是有特征筛选支撑的。

### Figure 3
可穿戴设备渲染图。设备本体是一个环绕后脑的头带，前向延伸到脸部和下颌区域，强调稳定贴合和可调节性。

### Figure 4
识别模型架构图。图中能看到从采集、预处理、特征变换到 1D CNN 分类的整条链路，说明作者把“信号工程”与“识别模型”放在同等重要的位置。

### Figure 5
activation maximization 的可视化。作者用它来展示不同类别在输入空间中对应的“原型信号”，这在当时是很典型的可解释性辅助证据。

### Figure 6
骨传导输出示意。它把系统闭环讲清楚了：输入是静默的，输出也是私密的，用户不需要把结果再暴露给周围环境。

### Figure 7
应用场景图。作者把系统拆成计算器、IoT 控制、媒体控制、日历、时钟、回复电话等任务，说明它被设计成一个通用个人接口，而不是单一 demo。

### Figure 8
10 个用户的 word accuracy boxplot。这里是论文最关键的定量结果证据，展示了准确率的分布、稳定性和用户间波动。

## 4) Experiments

### 数据与参与者
论文里其实有两层数据：
- **pilot study**：3 名参与者（1 female，平均年龄 29.33），先做 yes/no 二分类，主要用于找电极位置和验证可行性。
- **主数据集**：仍然是同样 3 名参与者，累计约 **31 小时**的 silently spoken text，用于训练更一般的分类器和减少 session 偏差。

作者逐步扩展词表，从 yes/no 到 reply/call/you，再到数字和运算符等多种语料集合。这个过程很重要，因为它说明系统不是一次性上开放词表，而是从可控子任务逐步堆出来的。

### 硬件与信号处理
论文给出了比较具体的硬件链路：
- 7 路信号来自 mental、inner/outer laryngeal、hyoid、inner/outer infra-orbital、buccal 等区域。
- 电极可用 gold plated silver 或 Ag/AgCl dry electrodes，论文主结果采用前者，因为数据质量更好。
- 参考电极放在 wrist 或 earlobe。
- 采样率 250 Hz，24x 增益，使用 4th order IIR Butterworth 1.3 Hz 到 50 Hz 过滤，并加 60 Hz notch。
- 还使用 ICA、整流、归一化和串接来进一步减少运动伪影。

这部分的关键信息是：作者没有把 EMG 当作“只要能采到就行”，而是很认真地在做一个面向真实佩戴的信号链。

### 特征与模型
识别模型大致是：
- 先做 running window average 去掉尖峰。
- 用 MFCC 风格的表征思路，把信号切成 0.025 s 窗、0.01 s 步长。
- 对功率谱做 mel filterbank，再用 DCT。
- 分类器是 1D CNN：每层 400 个 kernel size 3 的卷积，配合 max pooling，之后接全连接层和 sigmoid。
- 训练用 Adam，hidden layers 里用了 50% dropout。

这套做法说明作者实际上在用“语音识别的表示思想”迁移到 silent speech，而不是完全重新发明一个 EMG 解析框架。

### 任务设计
论文把应用组织成分层词表：
- Arithmetic：0-9 与四则运算、percent
- IoT：light on/off, fan on/off
- World clock：城市名
- Calendar：previous/next
- Chess：棋盘坐标和棋子符号
- Reply：一些常见会话短语

这里的关键不是词表本身，而是它们用 n-gram / Markov 风格的分层组织降低了瞬时分类空间。换句话说，作者通过“先识别应用，再识别词表”的层级结构，把问题从开放域识别变成了多个更小的封闭域任务。

### 结果
主结果是：
- **10 名参与者**
- 每人 **750 个 digits**，每个 digit 恰好出现 75 次
- **80/20** 随机训练/测试切分
- **10 次**训练测试重复
- 平均 word accuracy = **92.01%**
- 实时测试平均 latency = **0.427 s**

这个结果的意义在于，它并不是一个“离线高分但不可用”的模型。虽然延迟还不算极低，但已经接近可交互门槛，足以支撑闭环 demo。

### 局限
论文自己也写得比较清楚：
- 词表仍然很小，远不是开放词表 silent speech。
- 训练和评估仍然高度个性化，user-independent 能力没有解决。
- 实验是在相对静止场景下完成的，真正 ambulatory 场景没有验证。
- 设备虽然非侵入，但佩戴体验和长期舒适度仍然是工程问题。

## 5) Why it matters
这篇论文在今天仍然重要，原因不是它的语言模型先进，而是它定义了 silent speech 的系统形态：
- 输入侧：非侵入式 neuromuscular sensing
- 中间层：个性化识别与任务化词表
- 输出侧：骨传导私密反馈

这正好和现在的 EMG + LLM 思路形成了前后接力关系。今天的大模型更适合放在后端做重打分、语言约束、纠错和开放词表扩展；但 AlterEgo 证明的是，前端信号采集和闭环佩戴形态必须先成立。

换句话说，它不是“LLM 时代的答案”，但它是“LLM 时代之前，系统长什么样”的高质量模板。

## 6) Next steps
如果把这篇工作接到今天的研究线上，我会优先做这些方向：
1. 做 **user-independent + personalization** 的双阶段训练，而不是只做单用户模型。
2. 把输出从 closed vocabulary 扩展到 **open vocabulary**，并用 LLM 做后验重排。
3. 重新审视硬件舒适度，降低 conductive paste 和贴合调试成本。
4. 做真正的日常场景 longitudinal study，验证说话、走动、转头、咬合变化下的鲁棒性。
5. 把 silence 输入和 contextual output 结合起来，做更强的“语言意图 -> 任务执行”链路。

## 7) Scoring
- **Base:** 1
- **Quality bonus:** 2
- **Observation bonus:** 1
- **Final score:** **4/5**

### 为什么是 4/5
质量分给满 2 分，因为这篇论文同时给了系统架构、硬件实现、数据集、模型和应用演示，属于非常完整的系统论文。

观察分给 1 分，因为它的价值不只是“又一个 EMG 分类器”，而是把 silent speech 的产品形态、闭环方式和应用边界讲清楚了，对后续工作有直接参照意义。

但没有给到 5/5，是因为它的词表和评测仍然偏小，且用户独立性和真实场景验证都还没解决。
