# 产物 11：LLM 输出重写 `LanguageRefiner.refine`（Self-Refine，真实 DeepSeek）

## 能力说明
注入 `chat_fn` 后，多轮 Self-Refine：病句规则兜底 → AI 味检测 → 通则/规则/违禁词反馈（带规则 ID）→ LLM 改写 → 复检 → 收口。`chat_fn` 强制注入（None 抛 TypeError，fail-fast）。

## LLM 注入方式（本测试）
从 `~/.local/share/opencode/auth.json` 读取 `deepseek.key`，构造 OpenAI 兼容 `chat_fn` 调用 `deepseek-chat`。

## 实测输入 / 输出

**输入**：
```
总的来说，让我们一起赋能这个时代，点亮无限可能！
```

**输出**（真实 DeepSeek，max_rounds=1）：
```
这个时代不需要我们点燃什么。它已经在燃烧。我们所做的每一件诚实的事，都只是往火里添一根柴。
```

- 违禁词"总的来说/让我们一起/赋能/点亮/无限可能"全部去除 ✅
- 薇依式朴素文风（具体、不煽情、短句）✅
- 字符相似度：0.145（去 AI 味重写本质是大改，符合预期）

## 其它实测
- `make_refiner(chat_fn=None)` → 抛 `TypeError`（fail-fast）✅
- 默认加载薇依语料 10 条 ✅
- 干净文本（"墨水在水里散开…"）→ 不调用 LLM 直接返回 ✅
- 200 字窗口高频词重复检测 ✅

## 结果判定
✅ **可用 / 良好**。去 AI 味重写效果显著、文风符合薇依锚定。输出存在一定扩写（比输入长），属 LLM 行为。

## 发现与修复
无代码缺陷。**注意（风险 1）**：`refine()` 直调会产出大改重写；而 `gate_content(refiner=...)` 的 L2 因 95% 原意保持门槛会拒绝这类重写——两条路径语义不同（详见 `README.md` §四）。
