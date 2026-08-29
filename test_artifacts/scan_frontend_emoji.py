# -*- coding: utf-8 -*-
"""扫描前端 UI 源码中的装饰性 emoji（验收项③：前端图标用内联 SVG，不用 emoji）。

只统计「装饰性 emoji/符号」（⭐✅⚠❌🎯📊📝📌 等），排除：
  - 箭头 → ← ↑ ↓（词源推导链等正文内容，非图标）
  - 注释/文档里的符号（行首 // /* <!-- #）
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOTS = [
    (r"D:\wbo-workspace\paeg-teaching-materials\web", "14.2-teaching-web"),
    (r"D:\wbo-workspace\paeg-vocabulary-plugin\web", "14.3-vocab-web"),
    (r"D:\wbo-workspace\ai-job-search-derived-agent\product\web", "14.5-resume-web"),
]

# 装饰性 emoji/符号（排除箭头 U+2190-21FF）
DECO_RE = re.compile(
    "[\U0001F000-\U0001FAFF"   # emoji 主区
    "\U00002600-\U000026FF"    # misc symbols (☀☑⚠)
    "\U00002700-\U000027BF"    # dingbats (✅✈✂)
    "\U00002B00-\U00002BFF"    # misc symbols & arrows (⭐ 2B50)
    "\U0000FE0F"               # variation selector
    "]"
)

def scan_file(path):
    hits = []
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                for m in DECO_RE.finditer(line):
                    ch = m.group(0)
                    stripped = line.strip()
                    in_comment = (stripped.startswith("//") or stripped.startswith("/*")
                                  or stripped.startswith("*") or stripped.startswith("#")
                                  or stripped.startswith("<!--"))
                    hits.append((i, ch, in_comment, line.strip()[:70]))
    except Exception:
        pass
    return hits

total_ui = 0
for root, label in ROOTS:
    if not os.path.isdir(root):
        print(f"[skip] {label}: 不存在")
        continue
    files = []
    for dirpath, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("node_modules", "__pycache__", "uploads", ".git")]
        for n in names:
            if os.path.splitext(n)[1].lower() in (".html", ".js", ".css", ".ts", ".jsx", ".tsx", ".vue"):
                if not n.endswith(".min.js"):
                    files.append(os.path.join(dirpath, n))
    ui = 0
    for fp in sorted(files):
        hits = scan_file(fp)
        for ln, ch, in_comment, snippet in hits:
            if in_comment:
                continue
            ui += 1
            print(f"[UI-EMOJI] {label} :: {os.path.relpath(fp, root)}:{ln}  {ch!r}  {snippet}")
    total_ui += ui
    print(f"[{label}] 文件 {len(files)} 个；UI 装饰性 emoji 命中 {ui}")

print("\n" + "=" * 60)
print(f"TOTAL UI 装饰性 emoji: {total_ui}")
print("判定：0 → 前端图标全部内联 SVG，验收项③通过。")
