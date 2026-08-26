# paeg-lang-style

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-75%2F75%20%E2%9C%93-brightgreen.svg)](tests/)

**Chinese language quality plugin**: extensible grammar rules + dynamic forbidden-word list + LLM output rewriting. Detachable, independent, pluggable into any agent.

> [中文](README.md) | **English**

---

## What is it

`paeg-lang-style` is a **Chinese language quality module** with three layers:

| Layer | Capability | File |
|---|---|---|
| **Grammar rule constraints** (most important) | Lexical/syntactic/punctuation rules as **system prompts** — command the LLM to use complete words, complete syntax, sufficient adverbials. Everyone who uses it, concatenates it. | `rule_registry.py` + `prompts/builder.py` |
| **Forbidden-word fallback** | Dynamic forbidden-word list (AI-flavored phrases, empty buzzwords, fake-empathy verbs, cheap encouragement, internet slang) — the bottom line when LLM disobeys | `forbidden.py` |
| **Rewriting script** | Post-process LLM output: detect matched rules → feedback with rule IDs → multi-round Self-Refine | `refiner.py` + `gate.py` |

Zero host dependencies. Extracted from the PAEG educational agent (v0.12-v0.71 iterations), refactored as an independent plugin.

## ✨ Features

- 📜 **Extensible rule set**: rules externalized to `data/rules.json`, append-and-hot-reload (`RuleRegistry`)
- 🧠 **General-rule command**: lexical/syntactic/adverbial general rules let the LLM generalize, not memorize word-by-word replacements
- 🛡️ **Deterministic fallback**: explicit rules ("我在这里听着你。"→"我就在这里听你说说。")
- 🔁 **Rule-ID feedback loop**: rewrite feedback cites "violates #rule-lx-001"
- 🚫 **Dynamic forbidden-word list**: runtime add/remove + external JSON hot-load
- 🔧 **Injection design**: `chat_fn` mandatory injection — plug in your own LLM call
- 🎯 **Profile modes**: general / teaching / confessional
- 📏 **AI-taste detection**: burstiness / marker density / three-lists / em-dash / paragraph symmetry
- 🇨🇳 **8+ grammar rules**: GB/T 15834 punctuation + six disease-sentence types
- ✅ **75 tests** green + 20-sample behavior parity (string-equal vs PAEG original)

## 📦 Install

```bash
pip install -e /path/to/paeg-lang-style-plugin
# or add src/ to sys.path
```

Python 3.9+. Zero third-party runtime deps.

## 🚀 Quick Start

```python
from paeg_lang_style import RuleRegistry, make_refiner, gate_content

# 1. Grammar rules into your system prompt (everyone concatenates it)
system_prompt = "You are a tutor."
system_prompt += RuleRegistry().build_prompt("teaching")

# 2. Inject your LLM call (rewriting script)
def my_llm(system, user, max_tokens=800, **kw):
    return call_my_llm_api(system, user, max_tokens=max_tokens)
refiner = make_refiner(chat_fn=my_llm)

# 3. Post-process LLM output
clean = gate_content(raw_output, refiner=refiner)
```

## 🔌 Integration Guide for Other Projects

### A. Only grammar-rule constraints (system prompt)

```python
from paeg_lang_style import RuleRegistry
system += RuleRegistry().build_prompt("general")   # or "teaching"/"confessional"
```

### B. Rewriting script

```python
from paeg_lang_style import make_refiner, gate_content
refiner = make_refiner(chat_fn=my_llm)             # inject your LLM
clean = gate_content(output, refiner=refiner)
```

### C. Forbidden-word list

```python
from paeg_lang_style import ForbiddenWords
fb = ForbiddenWords()
fb.load_json("my_words.json")    # merge your words
hits = fb.detect(text)
```

### D. Extend rules (extensibility)

Edit `data/rules.json`, append a `Rule`, hot-reload:

```python
reg = RuleRegistry()
reg.load("data/rules.json")    # merge, append-take-effect
reg.watch("data/rules.json")   # mtime hot-reload
```

## 🧩 Extensibility

| Extension point | How | Mechanism |
|---|---|---|
| Grammar rules | Append to `data/rules.json` | `load()` merge + `watch()` hot-reload + `PAEG_RULES_PATH` override |
| Forbidden words | `load_json()` / `add()` / `remove()` | runtime dynamic |
| Corpus | Replace `weil_corpus.json` | `corpus_path` param |
| Profile | Add `profile_tags` to rule | `build_prompt(profile)` filter |
| LLM backend | Inject any `chat_fn` | mandatory injection |
| Rule-ID contract | Stable `id`, feedback cites it | loop for telemetry |

## 🛠️ Maintainability

- Zero host dependency, independently testable
- Old API compat (thin wrappers)
- 75 tests (load/hot-reload/detect/build/user-extension/corruption-tolerance)
- Behavior parity (string-equal vs PAEG original)
- Corruption-tolerant (keep last good rules, never clear-run)
- Token budget prevents prompt bloat

## 📚 Built-in Rules

| ID | Type | Category | Rule |
|---|---|---|---|
| `rule-lx-general-001` | general | lexical | Complete word forms (倦→疲倦) |
| `rule-sx-general-001` | general | syntactic | Complete sentence components |
| `rule-sx-general-002` | general | syntactic | **Sufficient adverbials** |
| `rule-pn-general-001` | general | punctuation | GB/T 15834 punctuation |
| `rule-lx-001~004` | explicit | lexical | 倦→疲倦 / 乏→疲乏 / 道出→说出来 / 探知→探索并了解 |
| `rule-sx-001~007` | explicit | syntactic | "听着你" gaffe / dangling object / collocation / translationese |
| `rule-pn-001` | explicit | punctuation | comma after 说 |

## ✅ Tests

```bash
python -m pytest tests/ -q
# 75: rule set load/hot-reload/detect/build/user-extension/corruption-tolerance + general rules + adverbials + parity
```

## 🙏 Credits

- **PAEG educational agent** (v0.12-v0.71) — source of this plugin
- **LanguageTool** — rule-declaration engine paradigm
- **textstat** — readability metric paradigm
- **GB/T 15834-2011** — Chinese punctuation national standard
- **Agent Skills** — progressive disclosure paradigm

## 📄 License

MIT © 2026 PAEG Team
