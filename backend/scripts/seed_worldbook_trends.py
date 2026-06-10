"""Seed worldbook entries and trend explorations for project 1 via API.

This makes Tab1 (Trends) and Tab2 (World) display non-empty content in the UI.
Run inside docker via: docker exec novel-ai-editor-backend python scripts/seed_worldbook_trends.py
Or run from host with: python scripts/seed_worldbook_trends.py (use direct API calls instead).
"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000/api/v1"
PROJECT_ID = 1


def post(path: str, body: dict) -> dict:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}") as r:
        return json.loads(r.read())


WORLDBOOK = [
    {
        "title": "灰雾禁律",
        "category": "setting",
        "content": "旧世界崩塌后，世界被灰雾覆盖。灰雾的深处有旧神遗骸和失落的城市，普通人一旦进入超过三十息，便会丧失神智。\n\n禁律院是唯一允许有组织地勘察灰雾的机构，其成员必须签订禁律契约：不可在雾中说出自己的真名，不可饮用未净化的水源，不可与雾中生灵产生情感纠葛。",
        "source_type": "core",
        "source_ref": "core_lore",
    },
    {
        "title": "档案司",
        "category": "organization",
        "content": "禁律院下设的核心部门之一，负责鉴定与封存从灰雾回收的卷宗、器具与生物标本。\n\n档案司按城市编号管理卷宗，编号越大表示危险等级越高。林雾所在的第七司专管边缘城市与未评级物品。",
        "source_type": "core",
        "source_ref": "org_lore",
    },
    {
        "title": "林雾",
        "category": "character",
        "content": "档案司第七司的青年鉴档员。性格内敛、观察力强，擅长从残缺的字句中推断真相。\n\n因童年意外在灰雾中存活一夜，被档案司破格录用，背负着'为什么他能活着回来'的谜团。",
        "source_type": "core",
        "source_ref": "protagonist",
    },
    {
        "title": "顾沉",
        "category": "character",
        "content": "禁律院执法司的年轻主事，外表冷峻，行动果断。\n\n对林雾抱有复杂的关注：既是监督，也是某种说不清的依靠。曾在一次雾区任务中与林雾共同遭遇险境。",
        "source_type": "core",
        "source_ref": "deuteragonist",
    },
    {
        "title": "白葵",
        "category": "character",
        "content": "档案司前代司主，老练沉稳，掌握着关于林雾童年意外的完整档案。\n\n对外是林雾的上司，对内是半个导师。常以'你问得太多了'回绝下属的疑问。",
        "source_type": "core",
        "source_ref": "mentor",
    },
    {
        "title": "裴衡",
        "category": "character",
        "content": "灰雾学者，对禁律的研究近乎狂热，私下追踪旧神遗骸的真相。\n\n与林雾合作过几次卷宗鉴定，提供理论支持，但林雾对他始终保持距离。",
        "source_type": "core",
        "source_ref": "ally",
    },
    {
        "title": "闻柯",
        "category": "character",
        "content": "执法司外勤，与林雾在多次雾区任务中搭档，擅长近战与陷阱识别。\n\n性格直爽，看不惯档案司的繁琐流程，与顾沉时常起争执。",
        "source_type": "core",
        "source_ref": "companion",
    },
    {
        "title": "残页",
        "category": "item",
        "content": "在灰雾深处回收的半页羊皮纸，上面的文字会在月光下缓慢变化。\n\n档案司至今无法破译，被列为第七司最高优先级研究对象。林雾的噩梦常常与此物相关。",
        "source_type": "core",
        "source_ref": "mystery",
    },
    {
        "title": "禁律锁",
        "category": "item",
        "content": "禁律院的核心器具，用于封锁卷宗与雾中物品的活性。\n\n每次启动需要消耗鉴档员的'心智余额'，使用过度会导致失眠、记忆空洞甚至更严重的后果。",
        "source_type": "core",
        "source_ref": "tool",
    },
    {
        "title": "第七城废墟",
        "category": "location",
        "content": "雾区边缘的旧城市，保留着相对完整的街巷结构，被档案司划定为'可勘察区'。\n\n实际勘察表明该城市存在异常时间流，越深入，停留的物理时间越长，心理时间越短。",
        "source_type": "core",
        "source_ref": "setting",
    },
]


TRENDS = [
    {
        "title": "当代悬疑+档案管理学跨界趋势",
        "source_scope": "web",
        "query_text": "分析近两年'档案/卷宗'类悬疑小说的爆款元素与读者偏好",
        "raw_findings": "近两年'档案管理'与'都市悬疑'结合的题材在豆瓣阅读、起点等平台均出现明显的热度回升。读者反馈集中的关键词包括：克制的叙事节奏、克制的情感表达、以小见大的案件结构。",
        "extracted_topics": json.dumps([
            {"insight": "档案、卷宗、禁律这一类机构化背景是稀缺设定，可与悬疑/惊悚完美嫁接"},
            {"insight": "读者对'为什么主角能活着'这类悬念更敏感，比单纯案件更吸引人"},
        ], ensure_ascii=False),
        "extracted_tags": json.dumps(["档案管理", "禁律", "悬疑", "克制冷峻", "克苏鲁", "机构博弈"], ensure_ascii=False),
        "suggested_directions": json.dumps([
            {"premise": "档案司新人在整理一批雾区回收卷宗时，发现所有案件都指向同一个人"},
            {"premise": "禁律机构内部的派系斗争与一个被掩盖的旧世界真相"},
        ], ensure_ascii=False),
        "status": "completed",
    },
    {
        "title": "克苏鲁系灰雾题材的视觉与氛围范式",
        "source_scope": "web",
        "query_text": "灰雾、雾区、不可名状氛围在中文小说中的最新呈现",
        "raw_findings": "近年中文创作中，'灰雾'与'禁区'类意象的接受度持续走高，搭配机构化处理（如禁律院、档案司）能有效降低传统克苏鲁的门槛。",
        "extracted_topics": json.dumps([
            {"insight": "灰雾不必完全照搬克苏鲁，可以本土化为'旧世界崩塌后的残留物'"},
            {"insight": "将不可名状之物'档案化'处理，能让读者更易代入"},
        ], ensure_ascii=False),
        "extracted_tags": json.dumps(["灰雾", "禁区", "档案", "机构", "不可名状"], ensure_ascii=False),
        "suggested_directions": json.dumps([
            {"premise": "灰雾是旧世界最后一场战争的副产品，禁律是为了防止它的扩散"},
        ], ensure_ascii=False),
        "status": "completed",
    },
    {
        "title": "冷静双男主组合的读者画像",
        "source_scope": "web",
        "query_text": "冷静克制系双男主在悬疑题材的读者反馈与商业表现",
        "raw_findings": "调研显示：冷静克制系双男主搭配在悬疑/惊悚题材中更受 22-35 岁高粘性读者欢迎，关键是要有'克制下的暗流'。",
        "extracted_topics": json.dumps([
            {"insight": "双男主的核心在于'是否在关键时刻'产生分歧而非表面冲突"},
            {"insight": "读者更偏爱通过档案、口供、笔记等'间接证据'感知关系变化"},
        ], ensure_ascii=False),
        "extracted_tags": json.dumps(["双男主", "克制冷峻", "悬疑", "群像"], ensure_ascii=False),
        "suggested_directions": json.dumps([
            {"premise": "档案员与执法者之间的信任在每一次卷宗鉴定中累积与动摇"},
        ], ensure_ascii=False),
        "status": "completed",
    },
]


def main() -> int:
    print("Seeding worldbook entries...")
    existing = {e["title"] for e in get(f"/projects/{PROJECT_ID}/worldbook")["data"]}
    for w in WORLDBOOK:
        if w["title"] in existing:
            print(f"  skip: {w['title']}")
            continue
        try:
            post(f"/projects/{PROJECT_ID}/worldbook", w)
            print(f"  + {w['title']}")
        except urllib.error.HTTPError as e:
            print(f"  ! {w['title']}: HTTP {e.code} {e.read().decode()[:200]}")

    print("Seeding trend explorations...")
    existing_t = {e["title"] for e in get(f"/projects/{PROJECT_ID}/trend-explorations")["data"]}
    for t in TRENDS:
        if t["title"] in existing_t:
            print(f"  skip: {t['title']}")
            continue
        try:
            post(f"/projects/{PROJECT_ID}/trend-explorations", t)
            print(f"  + {t['title']}")
        except urllib.error.HTTPError as e:
            print(f"  ! {t['title']}: HTTP {e.code} {e.read().decode()[:200]}")

    print()
    print("Verification:")
    wb = get(f"/projects/{PROJECT_ID}/worldbook")["data"]
    tr = get(f"/projects/{PROJECT_ID}/trend-explorations")["data"]
    print(f"  worldbook: {len(wb)} entries")
    print(f"  trends:    {len(tr)} explorations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
