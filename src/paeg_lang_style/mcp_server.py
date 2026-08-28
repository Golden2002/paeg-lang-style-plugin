# -*- coding: utf-8 -*-
"""paeg_lang_style.mcp_server — 语言规范插件 MCP server（可直接安装使用 ⭐）。

可及性标准（用户 §3.109 ⭐）：像 MCP server 一样**直接安装即可用**——
任何项目 `pip install` 后，在 MCP 客户端配置中声明本 server 即可接入，
零代码桥、零宿主依赖。

## 使用方式

```bash
# 方式 1：console_scripts 入口（pip install 后）
paeg-lang-style-mcp

# 方式 2：python -m 入口（源码运行）
python -m paeg_lang_style.mcp_server

# 方式 3：stdio 声明（MCP 客户端配置，如 config/mcp_servers.json）
# {"command": "python", "args": ["-m", "paeg_lang_style.mcp_server"], "cwd": "..."}
```

## 暴露的 MCP 工具

| 工具名 | 功能 | read/write |
|---|---|---|
| `normalize_text` | 文本语言规范守门（L0 规则 + L2 重写） | read |
| `language_policy_check` | AI 味检测 + 违禁词命中报告 | read |
| `forbidden_words` | 动态违禁词库管理（增/删/查） | write |
| `check_grammar` | 语法检查（8 类规则） | read |
| `check_ai_taste` | AI 味 5 维信号 | read |
| `build_style_prompt` | 系统提示词拼装（weil/lexicon/syntax/forbidden/规则集） | read |
| `list_rules` | 规则集清单（可扩充规则） | read |

## 接入 PAEG 主项目（config/mcp_servers.json 声明）

```json
{
  "mcpServers": {
    "paeg-lang-style": {
      "command": "python",
      "args": ["-m", "paeg_lang_style.mcp_server"],
      "cwd": "D:/wbo-workspace/paeg_project/paeg-lang-style-plugin"
    }
  }
}
```
"""
from __future__ import annotations

import json
import sys
from typing import Optional

# 允许从源码目录直接运行（python -m paeg_lang_style.mcp_server）
import os
_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

try:
    from fastmcp import FastMCP
except ImportError:
    FastMCP = None  # 未装 fastmcp 时软失败（不阻塞库导入）

from . import (
    gate_content, gate_short, fix_known_gaffes, check_ellipsis,
    detect_ai_taste, ForbiddenWords, get_style_prompt,
    RuleRegistry, make_refiner, LanguageRefiner,
)

SERVER_NAME = "paeg-lang-style"
_REFINER = None  # 惰性：仅当调用方注入 chat_fn 后可用 L2


def _get_refiner():
    """尝试获取 refiner（默认无 chat_fn 注入 → None，仅规则层）。"""
    global _REFINER
    if _REFINER is None:
        # 无 chat_fn → 无法 L2；保持规则层（L0）可用
        return None
    return _REFINER


def build_server() -> "FastMCP":
    """构建 MCP server（幂等）。"""
    if FastMCP is None:
        raise RuntimeError("fastmcp 未安装：pip install fastmcp")

    mcp = FastMCP(name=SERVER_NAME, strict_input_validation=True)

    @mcp.tool()
    def normalize_text(text: str, context: str = "", apply_l2: bool = True) -> str:
        """文本语言规范守门（L0 规则 + L2 重写）。
        修正病句（听着你→听你说说）、词法完整（倦→疲倦）、AI 腔；
        返回规范化文本。"""
        return gate_content(text, context=context, apply_l2=apply_l2, refiner=_get_refiner())

    @mcp.tool()
    def language_policy_check(text: str) -> dict:
        """AI 味检测 + 违禁词命中报告。
        返回 {ai_likelihood, verdict, forbidden_hits}。"""
        sig = detect_ai_taste(text)
        fb = ForbiddenWords()
        hits = fb.detect(text)
        return {
            "ai_likelihood": sig.ai_likelihood,
            "verdict": sig.verdict,
            "burstiness_cv": sig.burstiness_cv,
            "marker_density": sig.marker_density,
            "forbidden_hits": hits,
        }

    @mcp.tool()
    def forbidden_words(action: str, word: str = "", scope: str = "default") -> str:
        """动态违禁词库管理。action ∈ {list, add, remove, check}。
        - list: 返回当前词库前 50 条
        - add: 新增违禁词
        - remove: 移除违禁词
        - check: 检查 word 是否在词库"""
        fb = ForbiddenWords()
        if action == "list":
            return json.dumps(fb.words[:50], ensure_ascii=False)
        if action == "add":
            fb.add(word)
            return f"已新增违禁词: {word}"
        if action == "remove":
            fb.remove(word)
            return f"已移除违禁词: {word}"
        if action == "check":
            return f"{word} 在词库中" if word in fb.words else f"{word} 不在词库中"
        return f"未知 action: {action}（支持 list/add/remove/check）"

    @mcp.tool()
    def check_grammar(text: str) -> list:
        """语法检查（8 类规则：词法完整/动宾搭配/悬空宾语/无主语/复合句/介词/谓宾补足/语义残缺）。
        返回问题列表（每条含修正建议）。"""
        return check_ellipsis(text)

    @mcp.tool()
    def check_ai_taste(text: str) -> dict:
        """AI 味 5 维信号检测。返回 burstiness/marker/three-list/em-dash/paragraph 信号。"""
        sig = detect_ai_taste(text)
        return sig.as_dict()

    @mcp.tool()
    def build_style_prompt(section: str = "all", profile: str = "general") -> str:
        """系统提示词拼装（语法规则作为系统提示词核心，谁用都拼）。
        section ∈ {all, weil, lexicon, syntax, forbidden}；
        profile ∈ {general, teaching, confessional}——规则集按场景过滤。"""
        parts = []
        if section != "all":
            parts.append(get_style_prompt(section))
        reg = RuleRegistry()
        parts.append(reg.build_prompt(profile=profile))
        return "\n\n".join(parts)

    @mcp.tool()
    def list_rules() -> list:
        """可扩充规则集清单（RuleRegistry 全部规则）。
        返回 [{id, type, category, severity, enabled, source, profile_tags}]。"""
        reg = RuleRegistry()
        return [
            {k: r.get(k) for k in ("id", "type", "category", "severity", "enabled", "source", "profile_tags")}
            for r in reg.all()
        ]

    # ═══════════════════════════════════════════════════════════
    # §3.116 ⭐ R3 MCP 三原语补全：resources + prompts（此前仅 tools）
    # 生态插件铁则：Tools + Resources + Prompts 三类原语完整
    # ═══════════════════════════════════════════════════════════

    @mcp.resource("style-presets://list")
    def style_presets_resource() -> str:
        """文体预设列表（read-only 资源）。"""
        from .style_presets import list_styles
        return json.dumps(list_styles(), ensure_ascii=False)

    @mcp.resource("term-whitelist://list")
    def term_whitelist_resource() -> str:
        """术语白名单（read-only 资源）。"""
        from .term_guard import load_terms
        return json.dumps(sorted(load_terms()), ensure_ascii=False)

    @mcp.resource("rules://stats")
    def rules_stats_resource() -> str:
        """规则集统计（read-only 资源：总数 + 分类分布）。"""
        from collections import Counter
        reg = RuleRegistry()
        _cats = Counter(r.get("category", "") for r in reg.all())
        return json.dumps({"total": len(reg.all()), "by_category": dict(_cats)},
                          ensure_ascii=False)

    @mcp.prompt()
    def proofread_workflow(text: str, style: str = "general") -> str:
        """校对工作流模板（三级校对 + 文体适配）。"""
        return (
            f"请按三级校对体系校对以下文本（文体：{style}）：\n"
            "1. 基础级：错别字/标点/格式识别与修正\n"
            "2. 语法级：搭配不当/句式杂糅/语序不当/成分残缺\n"
            "3. 语义级：逻辑矛盾/概念混淆/歧义/用词不当（不改变原文核心意思）\n\n"
            f"待校对文本：\n{text}\n"
        )

    @mcp.prompt()
    def report(trace_json: str) -> str:
        """校对报告模板（修订痕迹 → 问题统计 + 建议）。"""
        return (
            "请根据修订痕迹生成校对报告：\n"
            "1. 问题类型统计（by_type）\n"
            "2. 每条修改的理由说明\n"
            "3. 修改建议（供人工复核）\n\n"
            f"修订痕迹：{trace_json}\n"
        )

    return mcp


def main():
    """CLI 入口：启动 MCP server（stdio 传输）。"""
    if FastMCP is None:
        print("错误：fastmcp 未安装，请先 pip install fastmcp", file=sys.stderr)
        sys.exit(1)
    server = build_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
