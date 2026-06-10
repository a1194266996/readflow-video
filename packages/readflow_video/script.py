import re

from .schemas import Scene, VideoProject

PATTERNS = [
    ("先别急着寻找答案", "真正改变人的，往往不是某个道理，而是你终于开始认真看见自己。"),
    ("把注意力拿回来", "少一点被外界推着走，多一点主动选择。你的时间花在哪里，生活就会长成什么样。"),
    ("降低无效消耗", "不是所有关系都值得解释，不是所有情绪都需要立刻回应。安静下来，判断会更清楚。"),
    ("建立自己的节奏", "别用别人的速度惩罚自己。能长期坚持的节奏，才是真正属于你的效率。"),
    ("用行动代替焦虑", "焦虑最怕具体的下一步。把问题拆小，然后今天只完成一个可以完成的动作。"),
    ("留下一个提醒", "人生不是突然变好的，而是在一次次选择里，慢慢变得更有方向。"),
    ("给未来一点耐心", "很多结果不会马上出现，但你反复做的事情，会在某一天替你说话。"),
    ("把复杂变简单", "当你不知道怎么选，就先问自己：这件事会让我更自由，还是更被消耗？"),
    ("珍惜自己的能量", "一个人最重要的资产，不只是时间，还有专注力、情绪和恢复能力。"),
    ("从今天开始", "不用等一个完美时机。现在能做的小改变，就是下一阶段的入口。"),
]


def _clean_prompt(prompt: str) -> str:
    compact = re.sub(r"\s+", " ", prompt).strip()
    return compact[:80] or "给普通人的成长提醒"


def generate_script(prompt: str, scene_count: int = 6, style: str = "小红书干货") -> VideoProject:
    topic = _clean_prompt(prompt)
    scenes: list[Scene] = [
        Scene(index=1, title=topic, body=f"如果你正在思考「{topic}」，这条视频想给你一个更清醒的角度。", duration=4.8)
    ]

    for i in range(1, scene_count):
        title, body = PATTERNS[(i - 1) % len(PATTERNS)]
        scenes.append(Scene(index=i + 1, title=title, body=body, duration=4.8))

    return VideoProject(title=topic, prompt=prompt, style=style, scenes=scenes[:scene_count])
