# -*- coding: utf-8 -*-
"""paeg_lang_style.ai_taste — AI 味检测器（纯算法，零外部依赖）。

从 PAEG 教育智能体 ai_taste_detector.py 提取（v0.13-v0.17）。
基于 2024-2026 实证信号：
- 句长变异度（burstiness）：AI 句子长度均匀（CV<0.35），人类长短交替（CV>0.45）
- 过渡词密度：AI 密集使用套话
- 三段式清单：AI 偏爱"三个要点"，人类（尤其薇依）用二/四/七
- 破折号滥用：AI 连用多个 em-dash
- 段落对称性：AI 段落等长，人类参差

用法：
    from paeg_lang_style.ai_taste import detect_ai_taste
    signals = detect_ai_taste(text)
    if signals.ai_likelihood > 0.5:  # 需要改写
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, asdict
from typing import List


# 常见 AI 痕迹信号词（来自实证清单）
AI_MARKERS = {
    "furthermore", "moreover", "additionally", "in addition",
    "it is worth noting", "it is important to note", "notably",
    "it should be noted", "it is essential to",
    "in conclusion", "to summarize", "in summary", "in essence",
    "leverage", "delve", "navigate", "utilize", "commence",
    "seamlessly", "cutting-edge", "transformative", "multifaceted",
    "robust", "comprehensive", "paramount",
    "it is clear that", "undoubtedly", "studies show that",
    "tapestry", "journey", "embark", "paradigm", "in the realm of",
    "when it comes to", "ultimately",
    # 中文 AI 痕迹
    "总的来说", "综上所述", "值得注意的是", "不难发现", "众所周知",
    "让我们", "让我们一起", "首先", "其次", "最后", "总而言之",
    "的海洋中", "点亮", "赋能", "拥抱", "精彩纷呈", "无限可能",
    # v0.16：AI 味形容词（"稳了"类——过度自信的口语化断言）
    "稳了", "拿捏了", "拿捏", "妥了", "没跑了", "就完事了", "妥妥的",
    "稳稳的", "完全没问题", "绝对没问题", "轻松拿下", "稳了稳了",
    "真的绝了", "绝了", "天秀", "神了", "牛", "牛啊", "绝绝子",
    "yyds", "YYDS", "秒懂", "狠狠", "狠狠拿捏",
    "非常棒", "棒极了", "太给力了", "给力",
    # AI 喜欢的高大上形容词
    "深刻", "全面", "系统", "本质", "本质地", "深远", "独到",
    # v0.19.13：没头没尾总结句
    "一句话总结", "一句话记住", "记住这一句", "牢记这一点", "牢记这几点", "核心就是",
    "说白了", "关键就在于", "简单来说", "简单点说", "重点来了", "划重点",
    "敲黑板", "注意了", "给你总结", "我来总结", "总结一下", "概括一下",
    "记住它", "记住这个", "记住这点",
    # v0.19.8：伪共情/AI腔动词
    "托住", "兜住", "兜底", "承托", "承接", "承接住", "承托感", "托举",
    "托底", "扶着", "搭把手", "靠岸", "安放", "安置", "安顿", "稳稳接住",
    "轻轻托住", "稳稳地", "轻轻地", "先接住", "先稳住", "先承接", "承接你的", "托住你的",
    "稳稳地陪你", "轻轻托住情绪", "稳稳接住你", "被看见", "听见你", "感知到", "体察到", "体悟到",
    "心酸", "心塞", "心碎", "共鸣", "同理心", "给你一个拥抱", "拍拍", "摸摸头",
    "揉揉", "不哭", "乖哦", "宝宝", "贴贴", "亲爱的", "宝贝", "牵挂你",
    "心疼得要死", "看见你", "感受到你", "赋予", "点亮", "点燃", "激活", "唤醒",
    "激发", "重塑", "迭代", "升级", "解锁", "开启", "踏上", "铸就",
    "成就", "缔造", "引领", "驱动", "沉淀", "蜕变", "绽放", "破茧",
    "进阶", "突围", "跃迁", "飞跃", "升华", "洞见", "洞察", "深耕",
    "聚焦", "锚定", "全方位", "一站式", "强赋能", "新范式", "探索之旅", "踏上旅程",
    "开启之旅", "你很棒", "你真优秀", "你真聪明", "你最棒", "冲鸭", "冲冲冲", "稳住我们能赢",
    "没事的", "别灰心", "别放弃", "再坚持一下", "你已经很努力了", "我看好你", "潜力股", "未来可期",
    "相信你", "你一定行", "你很厉害",
    '接住', '接住你的', '托住', '兜住', '稳住', '撑住', '托举',
    '接住情绪', '接住你的情绪', '抱抱', '拍拍', '摸摸头',
    '我看见了', '我看见你', '我听到了', '我听见你', '我感受到了', '感受到你的',
    '心疼你', '共情你', '同理你', '我懂你', '我理解你',
    '我知道你很难', '我知道你很痛苦',
    '赋能', '拥抱变化', '点燃', '点亮', '激活', '唤醒', '激发', '重塑',
    '迭代升级', '解锁', '开启旅程', '踏上旅程', '探索之旅',
    '加油', '你可以的', '相信自己', '你一定行', '冲鸭',
    # v0.17：低劣网络用语
    "绝绝子", "芭比Q了", "芭比Q", "栓Q", "我真的栓Q", "我真的会谢",
    "听我说谢谢你", "emo了", "破防", "退退退", "服了你个老六", "老六", "雪糕刺客",
    "嘴替", "大冤种", "尊嘟假嘟", "尊嘟", "假嘟", "哈基米",
    "搭子", "显眼包", "一整个爱住", "一整个震惊", "蚌埠住了", "绷不住了",
    "主打一个", "硬控", "水灵灵地", "红温", "搞抽象", "含金量还在上升",
    "古希腊掌管", "鼠鼠我啊", "精神状态领先", "脆皮NPC", "已老实", "依托构思",
    "这很难评", "纯路人", "塌房", "配享太庙", "纯爱战神", "泰酷辣",
    "多巴胺穿搭", "你人还怪好的", "你是懂", "薅羊毛", "偷感", "偷感很重",
    "偷感拉满", "草台班子", "那咋了", "班味儿", "班味", "电子榨菜",
    "命运的齿轮", "孔乙己", "公主请", "王子请", "特种兵式", "双向奔赴",
    "小孩哥", "小孩姐", "松弛感", "内卷", "躺平", "甩锅",
    "奥利给", "社死", "扎心了老铁", "戏精", "打call", "元宇宙",
    "666666", "666", "嘎嘎", "嘎嘎好", "嘎嘎香", "嘎嘎乱杀",
    "啊对对对", "没毛病", "太顶了", "直接给我冲", "给我哭死", "给我笑死",
    "治愈到", "整破防", "狠狠共情", "狠狠爱住", "踩雷", "上头",
    "下头", "整挺好", "属实是", "真的绝", "哇塞", "哇噻",
    "稳如老狗", "xswl", "awsl", "dbq", "xdm", "u1s1",
    "yysy", "sry", "plz", "zqsg", "yygq", "ssfd",
    "nsdd", "bhys", "srds", "kdl", "kswl", "xmsl",
    "hxd", "hxdm", "bbl", "bbzl", "gkd", "pyq",
    "pph", "xjj", "xj", "sj", "bp", "ky",
    "rs", "plmm", "yxh", "ssmy", "nbcs", "uu",
    "yjjc", "szd", "tql", "tnl", "yjgj", "xsl",
    "xfxy", "cy", "qs", "宝子", "家人们", "老铁",
    "兄弟姐妹", "亲们", "闭眼入", "必入", "上车", "链接放下面",
    "三连", "懂的都懂", "不懂的问我", "划走你就亏了", "家人们冲", "抄作业",
    "啵啵间", "赚米", "满满正能量", "真的超赞", "福利", "抓手",
    "闭环", "沉淀", "打通", "颗粒度", "对齐", "拉齐",
    "拉通", "倒逼", "复盘", "画饼", "吃透", "死磕",
    "击穿", "引爆", "心智", "漏斗", "打法", "链路",
    "矩阵", "触达", "透传", "串联", "包装", "履约",
    "协同", "反哺", "共建", "共创", "解耦", "拆解",
    "摸鱼", "划水", "收割", "复利", "风口", "赛道",
    "拉一拉", "推一推", "不可否认的是", "老实说", "更有意思的是", "在许多情况下",
    "在某种程度上", "至关重要", "意义重大", "标志着", "奠定基础", "不断变化的格局",
    "不可或缺", "根植于", "你并不孤单", "开启一段", "踏上", "之旅",
    "整活", "绝活", "活久见", "爷青回", "爷青结", "破圈",
    "出圈", "圈粉", "涨知识", "手慢无", "买它", "冲冲冲",
    "起飞", "爆了", "炸了", "针不戳", "集美", "好家伙",
    "就这", "就这就这", "我滴妈", "稀碎", "白给", "翻车",
    "翻车现场", "打脸", "啪啪打脸", "凡尔赛", "柠檬精", "酸了",
    "恰柠檬", "吃瓜", "吃瓜群众", "前排吃瓜", "蹲一个", "插眼",
    "码住", "走起", "搞起", "安排上", "卷起来", "很卷",
    "太卷", "卷王", "卷不动", "佛系", "随缘", "摆烂",
    "开摆", "摆烂王", "精神内耗", "PUA", "钝感力", "情绪价值",
    "多巴胺", "氛围感", "高级感", "仪式感", "治愈系", "小确幸",
    "小确丧", "网抑云", "深夜emo", "破大防", "笑不活了", "笑死",
    "笑yue了", "啊这", "好嘞", "好滴", "okk", "收到收到",
    "跪了", "跪求", "求求了", "球球了", "大佬", "巨佬",
    "大神", "牛批", "牛啤", "牛皮", "秀儿", "陈独秀",
    "带节奏", "带偏", "歪楼", "催更", "咸鱼", "逆袭",
    "黑马", "爆冷", "顶流", "平替", "刺客", "盲盒",
    "欧皇", "非酋", "欧气", "出金", "保底", "抽卡",
    "氪金", "爆肝", "肝帝", "冲分", "上分", "排位",
    "青铜", "王者", "菜鸡", "菜狗", "小趴菜", "带飞",
    "躺赢", "C位", "出道", "爱豆", "墙头", "本命",
    "应援", "打榜", "控评", "脱粉", "路人缘", "爆款",
    "秒杀", "种草", "拔草", "剁手", "买买买", "限定",
    "联名", "梦幻联动", "神仙组合", "神仙打架", "颜值担当", "天花板",
    "封神", "封顶", "断层", "降维打击", "格局打开", "格局小了",
    "碾压", "吊打", "完爆", "神操作", "骚操作", "操作拉满",
    "拉满", "拉胯", "辣眼睛", "瞎眼", "迷惑行为", "大受震撼",
    "原地去世", "当场去世", "笑死我了", "哈哈哈", "2333", "233",
    "草率了", "大意了", "背锅", "背锅侠", "甩锅侠", "接盘",
    "接盘侠", "冤大头", "韭菜", "割韭菜", "智商税", "交学费",
    "长记性", "涨记性", "不长记性", "长点心", "走点心", "上点心",
}


@dataclass
class AITasteSignals:
    burstiness_cv: float          # 句长变异系数
    marker_density: float         # 过渡词密度（每千字）
    three_list_count: int         # 三段式清单出现次数
    em_dash_count: int            # 破折号数量
    paragraph_cv: float           # 段落长度变异
    ai_likelihood: float          # 综合 AI 概率 0-1
    verdict: str                  # AI / Mixed / Human

    def as_dict(self):
        return asdict(self)


def _word_count(s: str) -> int:
    return len(re.findall(r"[\w\u4e00-\u9fff]+", s))


def _sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _paragraphs(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def measure_burstiness(text: str) -> float:
    """句长变异系数：AI<0.35，人类>0.45。"""
    lengths = [_word_count(s) for s in _sentences(text)]
    if len(lengths) < 3:
        return 0.5
    mean = statistics.mean(lengths)
    if mean == 0:
        return 0.5
    return statistics.pstdev(lengths) / mean


def measure_marker_density(text: str) -> float:
    """过渡词密度（每千字）。AI>5，人类<1.5。"""
    words = max(_word_count(text), 1)
    lower = text.lower()
    hits = sum(lower.count(m) for m in AI_MARKERS)
    return (hits / words) * 1000.0


def count_three_lists(text: str) -> int:
    """三段式清单：'三个要点/三步/三种' 或 'firstly, secondly, thirdly'。"""
    patterns = [
        r"三个", r"三步", r"三种", r"三点", r"three (?:key|main|steps|reasons|benefits)",
        r"firstly.*secondly.*thirdly",
        r"一、.*二、.*三、",
    ]
    count = 0
    for pat in patterns:
        count += len(re.findall(pat, text, re.I))
    return count


def count_em_dashes(text: str) -> int:
    """破折号数量（AI 偏爱多连用）。"""
    return len(re.findall(r"—", text)) + len(re.findall(r"——", text))


def measure_paragraph_symmetry(text: str) -> float:
    """段落长度变异：AI 段落等长（低 CV）。"""
    paras = _paragraphs(text)
    if len(paras) < 3:
        return 0.5
    lens = [_word_count(p) for p in paras]
    mean = statistics.mean(lens)
    if mean == 0:
        return 0.5
    return statistics.pstdev(lens) / mean


def detect_ai_taste(text: str) -> AITasteSignals:
    """综合检测。返回各信号 + 综合 AI 概率。"""
    if not text or not text.strip():
        return AITasteSignals(0.5, 0, 0, 0, 0.5, 0.3, "Human")

    cv = measure_burstiness(text)
    marker_density = measure_marker_density(text)
    three_lists = count_three_lists(text)
    em_dashes = count_em_dashes(text)
    para_cv = measure_paragraph_symmetry(text)

    # 短文本（<30字）：只靠词库信号判断
    if len(text) < 30:
        marker_ai = max(0.0, min(1.0, marker_density / 8.0))
        composite = 0.6 * marker_ai + 0.4 * min(1.0, three_lists / 2.0)
        verdict = "AI" if composite >= 0.5 else ("Mixed" if composite >= 0.3 else "Human")
        return AITasteSignals(
            burstiness_cv=round(cv, 3), marker_density=round(marker_density, 2),
            three_list_count=three_lists, em_dash_count=em_dashes,
            paragraph_cv=round(para_cv, 3), ai_likelihood=round(composite, 3), verdict=verdict,
        )

    burst_ai = max(0.0, min(1.0, (0.45 - cv) / 0.30))
    marker_ai = max(0.0, min(1.0, marker_density / 8.0))
    three_ai = min(1.0, three_lists / 3.0)
    dash_ai = min(1.0, max(0, em_dashes - 2) / 4.0)
    para_ai = max(0.0, min(1.0, (0.40 - para_cv) / 0.30))

    # 加权综合（结构>词汇>模式）
    composite = (
        0.20 * burst_ai
        + 0.40 * marker_ai
        + 0.20 * three_ai
        + 0.10 * dash_ai
        + 0.10 * para_ai
    )

    if composite >= 0.5:
        verdict = "AI"
    elif composite >= 0.3:
        verdict = "Mixed"
    else:
        verdict = "Human"

    return AITasteSignals(
        burstiness_cv=round(cv, 3),
        marker_density=round(marker_density, 2),
        three_list_count=three_lists,
        em_dash_count=em_dashes,
        paragraph_cv=round(para_cv, 3),
        ai_likelihood=round(composite, 3),
        verdict=verdict,
    )
