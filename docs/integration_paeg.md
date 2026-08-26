# 接入 PAEG 教育智能体（integration guide）

> 独立开发的语言规范插件如何**方便接入教育智能体**（插件化水平的体现）。

## 核心原则（R20 · 零破坏铁律）

1. **唯一适配层**：PAEG 主项目所有语言规范调用统一走 `infra/lang_plugin_bridge.py`
2. **静默回退**：插件未挂载（import 失败）→ 回退 PAEG 原实现，行为 100% 等价
3. **旧文件永不删除**：`services/lang_gate.py` / `language_refiner.py` / `prompts.LANGUAGE_STYLE` 保留为回滚备份

## 接入步骤

### 步骤 1：放置插件

```powershell
# 插件与主项目平级
D:\wbo-workspace\paeg_project\
├── 05_实现原型\          # PAEG 主项目
└── paeg-lang-style-plugin\   # 本插件
```

### 步骤 2：加载插件

PAEG 启动时把插件 src 加入 path（`server.py` 或 `config/settings.py`）：

```python
import os, sys
_PLUGIN_SRC = os.path.join(os.path.dirname(__file__), "..", "paeg-lang-style-plugin", "src")
if os.path.isdir(_PLUGIN_SRC) and _PLUGIN_SRC not in sys.path:
    sys.path.insert(0, _PLUGIN_SRC)
```

或安装为包：`pip install -e D:\wbo-workspace\paeg_project\paeg-lang-style-plugin`

### 步骤 3：改造调用点（经桥）

| 原调用 | 改造为 | 位置 |
|---|---|---|
| `from services.lang_gate import lang_gate_content` | `from infra.lang_plugin_bridge import gate_content` | 生成链路 |
| `from services.lang_gate import lang_gate_short` | `from infra.lang_plugin_bridge import gate_short` | 短文本 |
| `from prompts import LANGUAGE_STYLE` | `from infra.lang_plugin_bridge import get_style_prompt` | presenter/affection |
| `LanguageRefiner(llm)` | `make_refiner(chat_fn=_safe_chat, llm=llm)` | subagents |
| `from language_refiner import fix_known_gaffes` | `from infra.lang_plugin_bridge import fix_known_gaffes` | 各处 |

### 步骤 4：验证

```powershell
# 1. 插件挂载模式
python -c "from infra.lang_plugin_bridge import plugin_active; print(plugin_active())"  # True

# 2. 回退模式（移除插件 path 后）→ plugin_active() False，行为不变

# 3. 行为一致性（vs PAEG 原实现）
python -m pytest ..\paeg-lang-style-plugin\tests\test_parity.py -q

# 4. PAEG 回归
python audit_check.py
python smoke_test.py
python -m pytest tests/ -q
```

## 版本同步

- 插件版本 v0.1.x ↔ PAEG v0.42+ 绑定
- 更新插件 → 更新 README（8 条规则）→ 跑 parity 测试 → 推送插件仓库
- PAEG 端桥文件无需改动（接口稳定）

## 回滚

插件出问题 → 移除 path 注入 → 桥自动回退 PAEG 原实现 → 零破坏。
（R20 铁律的工程化兑现：桥是叠加层，不是替换层。）

## 桥 API 一览

```python
gate_content(text, context="", apply_l2=True, refiner=None, polish_fn=None) -> str
gate_short(text, context="", refiner=None, polish_fn=None) -> str
fix_known_gaffes(text) -> str
check_ellipsis(text) -> list
get_style_prompt(section="all") -> str
make_refiner(*, chat_fn, llm=None, corpus_path=None) -> LanguageRefiner
detect_ai_taste(text) -> AITasteSignals
forbidden_words_detect(text) -> list
plugin_active() -> bool
```
