"""为驾驶舱、故事脉络、章节小结等视图填充完整的演示数据。

执行方式（容器内）::

    docker compose exec backend python scripts/seed_full_demo.py

幂等：重复执行不会重复插入数据。
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 让脚本能 ``import app.*``（与其它脚本保持一致）
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select  # noqa: E402

from app.db.base import SessionLocal, create_db_and_tables  # noqa: E402
from app.models.ai_task import AITask, TaskLog, TaskStep  # noqa: E402
from app.models.chapter import Chapter  # noqa: E402
from app.models.chapter_version import ChapterVersion  # noqa: E402
from app.models.character import Character  # noqa: E402
from app.models.character_relationship import CharacterRelationship  # noqa: E402
from app.models.plot_line import PlotLine  # noqa: E402
from app.models.project import NovelProject  # noqa: E402
from app.services.graph_service import create_character_relationship, sync_character_to_neo4j  # noqa: E402
from app.schemas.graph import CharacterRelationshipCreate  # noqa: E402


# ----------------------------------------------------------------------------
# Demo 内容：仅供前端展示
# ----------------------------------------------------------------------------
PROJECT_INFO = {
    "name": "蒸汽审判者",
    "genre": "蒸汽奇幻",
    "theme": "禁术审判与秩序裂缝",
    "target_audience": "网文读者",
    "writing_style": "紧张、克制、悬疑推进",
    "tone": "暗色、克制、压迫感",
    "summary": "近代蒸汽都市与审判体系并存的奇幻世界。一名档案记录员在追查失踪导师的过程中，意外卷入禁术审判的核心旋涡。",
    "world_setting": (
        "灰雾笼罩的镜湖城，三大审判署以「裂隙巡察」为名维护秩序，"
        "蒸汽炉心驱动一切工业，而被称作「旧语法」的禁术仍残留在地底管道之中。"
    ),
}

CHARACTERS = [
    {"name": "林雾", "role_type": "protagonist", "identity": "档案记录员", "status": "active",
     "personality": "冷静、敏锐、略带反叛", "background": "审判署见习记录员，导师失踪后开始自学旧语法。"},
    {"name": "顾沉", "role_type": "executor", "identity": "审判署执行官", "status": "active",
     "personality": "克制、忠诚、压抑情感", "background": "负责裂隙巡察的执行官，与林雾有说不清的过往。"},
    {"name": "闻柯", "role_type": "informant", "identity": "地下情报商", "status": "active",
     "personality": "油滑、贪婪、但讲信义", "background": "垄断地下管道的旧语法信息，与林雾做过多笔交易。"},
    {"name": "白葵", "role_type": "ally", "identity": "蒸汽炉维修工", "status": "active",
     "personality": "热情、话痨、忠诚", "background": "林雾的童年好友，负责炉心深处的日常维护。"},
    {"name": "裴衡", "role_type": "antagonist", "identity": "审判署次官", "status": "active",
     "personality": "阴沉、算计、深藏不露", "background": "推动禁术法案的核心人物之一，导师失踪案的幕后推手。"},
]

RELATIONSHIPS = [
    ("林雾", "顾沉", "暧昧", 0.65, "童年相遇，分离多年，再次相见时彼此戒备却也彼此依赖。"),
    ("林雾", "闻柯", "交易", 0.85, "用秘密档案换取地下情报的等价交换。"),
    ("林雾", "白葵", "挚友", 0.95, "可以托付后背的儿时同伴。"),
    ("林雾", "裴衡", "敌对", 0.9, "导师失踪案的嫌疑人，林雾在暗中追查。"),
    ("顾沉", "裴衡", "服从", 0.5, "执行官对次官的命令保持惯性服从，但内心开始动摇。"),
    ("顾沉", "白葵", "旧识", 0.4, "曾在一次炉心事故中合作救援。"),
]

# 主剧情线
MAIN_PLOT_LINES = [
    {"title": "导师失踪之谜", "plot_type": "main", "priority": 90,
     "summary": "林雾的导师贺无声在一场裂隙巡察中失联，只留下半张被撕毁的档案。",
     "goal": "找到导师的下落并揭示审判署掩盖的真相。",
     "conflict": "调查越深入，受到的阻力越大，裴衡开始将林雾列为嫌疑人。",
     "stakes": "若不能查清真相，下一个失踪的便是林雾本人。",
     "start_phase": "第一章 雾中档案室", "end_phase": "第十二章 真相残页", "status": "active"},
    {"title": "旧语法觉醒", "plot_type": "subplot", "priority": 75,
     "summary": "林雾在追寻真相的过程中逐渐唤醒体内沉睡的旧语法能力。",
     "goal": "在不触犯禁术法案的前提下控制并理解旧语法。",
     "conflict": "每次动用旧语法都会留下「灰雾印记」，被审判署的巡察察觉。",
     "stakes": "失控可能波及整个镜湖城的炉心稳定。",
     "start_phase": "第三章 灰雾初现", "end_phase": "第十一章 旧语者", "status": "active"},
    {"title": "顾沉的抉择", "plot_type": "character_arc", "priority": 70,
     "summary": "执行官顾沉在命令与个人情感之间逐渐倾斜。",
     "goal": "查清次官裴衡的真正图谋。",
     "conflict": "一旦违抗命令将失去执行官身份并牵连家人。",
     "stakes": "若无法自证清白，将沦为「叛律者」处刑。",
     "start_phase": "第四章 巡察笔记", "end_phase": "第十五章 执剑者的觉醒", "status": "active"},
]

# 章节大纲（包含分场景小结）
CHAPTERS = [
    {
        "chapter_no": 1, "title": "雾中档案室", "status": "completed", "word_count": 1820,
        "objective": "林雾接到导师失踪的通报，独自进入封存的档案室寻找线索。",
        "conflict": "档案室被加封了禁律锁，仅记录员权限无法打开。",
        "summary": "林雾在档案室中找到导师留下的半张纸，并第一次感知到「灰雾」的脉动。",
        "scenes": [
            {"title": "晨雾中的卷宗", "summary": "林雾在灰雾笼罩的镜湖城街道上接到导师失踪的消息，决定前往档案室。", "pov": "林雾", "word_count": 580, "mood": "压抑、紧张"},
            {"title": "禁律锁前", "summary": "档案室被加封禁律锁，林雾凭借见习记录员权限勉强进入其中。", "pov": "林雾", "word_count": 540, "mood": "惊惧、专注"},
            {"title": "半张残页", "summary": "在导师旧抽屉中发现被撕毁的档案，纸背上浮现出旧语符号。", "pov": "林雾", "word_count": 700, "mood": "悚然、好奇"},
        ],
    },
    {
        "chapter_no": 2, "title": "地下管道的温度", "status": "completed", "word_count": 1950,
        "objective": "林雾通过闻柯拿到地下管道的旧地图，意外见到白葵。",
        "conflict": "地下管道被审判署划为禁入区，闯入将面临拘役。",
        "summary": "林雾与白葵在地下管道重逢，得知导师失联当晚曾来过这里。",
        "scenes": [
            {"title": "情报商的门", "summary": "林雾在闻柯的暗室中用档案换取旧管道地图。", "pov": "林雾", "word_count": 620, "mood": "算计、紧张"},
            {"title": "蒸汽炉心的回响", "summary": "深入地下，白葵在炉心维修间歇透露导师失联当晚的异常。", "pov": "白葵", "word_count": 680, "mood": "神秘、回忆"},
            {"title": "墙上的旧语法", "summary": "林雾第一次在管道壁上看见旧语法刻痕，灰雾印记开始隐隐灼热。", "pov": "林雾", "word_count": 650, "mood": "压抑、诡异"},
        ],
    },
    {
        "chapter_no": 3, "title": "灰雾初现", "status": "completed", "word_count": 1780,
        "objective": "林雾在调查中被巡察执行官顾沉拦截，第一次正面交锋。",
        "conflict": "林雾无法解释为何持有禁入区通行痕迹，又无法暴露旧语能力。",
        "summary": "顾沉暂时放行林雾，但留下警告。两人过去的关系被提及。",
        "scenes": [
            {"title": "蒸汽钟敲七下", "summary": "林雾在出口处被顾沉拦截，对方手持裂隙巡察的令牌。", "pov": "顾沉", "word_count": 560, "mood": "对峙、克制"},
            {"title": "档案与嫌疑", "summary": "林雾以档案研究为由掩盖行踪，顾沉半信半疑。", "pov": "林雾", "word_count": 620, "mood": "谨慎、机锋"},
            {"title": "灰雾的脉动", "summary": "在被放行瞬间，林雾手臂上的旧语法印记短暂浮现，被顾沉瞥见。", "pov": "林雾", "word_count": 600, "mood": "惊惧、心悸"},
        ],
    },
    {
        "chapter_no": 4, "title": "巡察笔记", "status": "completed", "word_count": 2010,
        "objective": "林雾借阅导师的旧巡察笔记，发现导师调查的方向指向审判署内部。",
        "conflict": "记录员无权调阅高阶巡察笔记，林雾只能偷取。",
        "summary": "林雾冒极大风险取回笔记，发现导师怀疑的矛头直指次官裴衡。",
        "scenes": [
            {"title": "夜班记录员", "summary": "林雾在深夜伪装成夜班记录员潜入调阅室。", "pov": "林雾", "word_count": 660, "mood": "紧张、专注"},
            {"title": "导师的笔迹", "summary": "笔记中提到次官裴衡与禁术法案的异常关联。", "pov": "林雾", "word_count": 700, "mood": "震惊、推理"},
            {"title": "裂隙巡察的谎言", "summary": "林雾意识到导师失联可能与裂隙巡察的「意外」报告有关。", "pov": "林雾", "word_count": 650, "mood": "冷峻、压抑"},
        ],
    },
    {
        "chapter_no": 5, "title": "庭上对质", "status": "completed", "word_count": 2140,
        "objective": "林雾决定以档案员的身份在审判庭上提出对次官的质疑。",
        "conflict": "档案员的指控权限极低，几乎没有成功的可能。",
        "summary": "林雾在庭上公开了导师的笔记，但被次官以程序性理由驳回。",
        "scenes": [
            {"title": "庭前三问", "summary": "林雾在进入审判庭前反复确认自己的证词。", "pov": "林雾", "word_count": 700, "mood": "决绝、克制"},
            {"title": "次官的反击", "summary": "裴衡以档案员越权为由要求驳回，并暗示林雾可能接触禁术。", "pov": "裴衡", "word_count": 720, "mood": "压迫、阴鸷"},
            {"title": "庭外的雨", "summary": "庭审被驳回后，林雾站在审判署外的雨中，与顾沉再次相遇。", "pov": "林雾", "word_count": 720, "mood": "失落、坚定"},
        ],
    },
    {
        "chapter_no": 6, "title": "炉心深处的呼救", "status": "in_progress", "word_count": 760,
        "objective": "白葵紧急联系林雾，炉心深处出现异常震动。",
        "conflict": "若炉心失控，整个镜湖城将陷入瘫痪。",
        "summary": "林雾跟随白葵进入炉心核心，发现旧语法刻痕正在蔓延。",
        "scenes": [
            {"title": "白葵的暗号", "summary": "白葵用蒸汽哨发出暗号，召来林雾。", "pov": "白葵", "word_count": 360, "mood": "紧张、急迫"},
            {"title": "炉心裂隙", "summary": "林雾在炉心深处看到旧语刻痕正在扩展，灰雾印记开始剧烈灼烧。", "pov": "林雾", "word_count": 400, "mood": "震撼、恐惧"},
        ],
    },
    {
        "chapter_no": 7, "title": "再入档案室", "status": "planned", "word_count": 0,
        "objective": "林雾决定在导师留下的残页基础上拼凑出完整线索。",
        "conflict": "档案室已被加强封锁，需借助顾沉的权限。",
        "summary": "待续：林雾冒险再入档案室，导师的真正死因浮出水面。",
        "scenes": [
            {"title": "暗号与回信", "summary": "林雾通过白葵向顾沉传递暗号，等待其回应。", "pov": "林雾", "word_count": 0, "mood": "焦灼"},
        ],
    },
]


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def _ensure_project(db) -> NovelProject:
    project = db.scalar(select(NovelProject).where(NovelProject.name == PROJECT_INFO["name"]))
    if project is not None:
        return project
    project = NovelProject(**PROJECT_INFO)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _ensure_characters(db, project_id: int):
    existing = {c.name: c for c in db.scalars(select(Character).where(Character.project_id == project_id))}
    created = []
    for spec in CHARACTERS:
        if spec["name"] in existing:
            continue
        character = Character(project_id=project_id, **spec)
        db.add(character)
        db.commit()
        db.refresh(character)
        try:
            sync_character_to_neo4j(character)
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] sync neo4j failed for {character.name}: {exc}")
        existing[character.name] = character
        created.append(character)
    return existing


def _ensure_relationships(db, project_id: int, characters):
    existing_pairs = {
        (r.source_character_id, r.target_character_id, r.relation_type)
        for r in db.scalars(select(CharacterRelationship).where(CharacterRelationship.project_id == project_id))
    }
    for source_name, target_name, relation_type, intensity, note in RELATIONSHIPS:
        if source_name not in characters or target_name not in characters:
            continue
        src = characters[source_name]
        tgt = characters[target_name]
        if (src.id, tgt.id, relation_type) in existing_pairs:
            continue
        try:
            create_character_relationship(
                db,
                project_id,
                CharacterRelationshipCreate(
                    source_character_id=src.id,
                    target_character_id=tgt.id,
                    relation_type=relation_type,
                    intensity=intensity,
                    note=note,
                ),
            )
            existing_pairs.add((src.id, tgt.id, relation_type))
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] failed to create relationship {source_name}->{target_name}: {exc}")


def _ensure_plot_lines(db, project_id: int):
    existing_titles = {
        p.title for p in db.scalars(select(PlotLine).where(PlotLine.project_id == project_id))
    }
    for spec in MAIN_PLOT_LINES:
        if spec["title"] in existing_titles:
            continue
        line = PlotLine(project_id=project_id, **spec)
        db.add(line)
        db.commit()
    return list(db.scalars(select(PlotLine).where(PlotLine.project_id == project_id)))


# 原 scenes 列表的拷贝（避免 ``_ensure_chapters`` 中 pop 副作用）
CHAPTERS_BY_NO = {spec["chapter_no"]: spec for spec in CHAPTERS}


def _ensure_chapters(db, project_id: int):
    existing = {
        c.chapter_no: c
        for c in db.scalars(select(Chapter).where(Chapter.project_id == project_id))
    }
    for spec in CHAPTERS:
        # 拷贝，避免 pop 影响外层 CHAPTERS 列表
        spec_copy = {k: v for k, v in spec.items() if k != "scenes"}
        if spec["chapter_no"] in existing:
            ch = existing[spec["chapter_no"]]
            for k, v in spec_copy.items():
                setattr(ch, k, v)
            db.commit()
        else:
            ch = Chapter(project_id=project_id, **spec_copy)
            db.add(ch)
            db.commit()
            db.refresh(ch)
            existing[ch.chapter_no] = ch
    return list(db.scalars(select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.chapter_no)))


def _ensure_scene_plot_lines(db, project_id: int, chapters):
    """每个章节下的「场景」是 plot_line 行，plot_type=chapter_scene, goal 中嵌入 chapter_scene_for 标记。"""
    # 一次性删除所有 chapter_scene，再统一重新插入（避免循环中互相覆盖）
    db.execute(
        delete(PlotLine).where(
            PlotLine.project_id == project_id,
            PlotLine.plot_type == "chapter_scene",
        )
    )
    db.commit()
    for ch in chapters:
        spec = CHAPTERS_BY_NO.get(ch.chapter_no)
        if spec is None:
            continue
        scenes = spec.get("scenes") or []
        if not scenes:
            continue
        for idx, sc in enumerate(scenes, start=1):
            pov = sc.get("pov") or ""
            mood = sc.get("mood") or ""
            wc = sc.get("word_count") or 0
            goal = (
                f"chapter_scene_for:{ch.id}\n\n"
                f"POV: {pov}\n"
                f"字数: {wc}\n"
                f"情绪: {mood}"
            )
            line = PlotLine(
                project_id=project_id,
                title=f"第{ch.chapter_no}章 · 场景{idx} · {sc.get('title', '')}",
                plot_type="chapter_scene",
                summary=sc.get("summary", ""),
                goal=goal,
                conflict=sc.get("conflict") or ch.conflict,
                stakes=sc.get("pov") or "",
                start_phase=f"chapter:{ch.chapter_no}",
                end_phase=f"chapter:{ch.chapter_no}",
                status=ch.status,
                priority=10 + idx,
            )
            db.add(line)
        db.commit()


def _ensure_chapter_content(db, project_id: int, chapters):
    """为已完成的章节生成真小说正文（叙事性散文，≥ 1500 字/章）。
    用于驾驶舱角色频次、字数统计、Tab3 章节正文展示。

    每章结构：
      - 标题 + 开场人物/环境刻画
      - 每个 scene 块：场景标题 + 设定 + 概要 + 感官 + 心理 + 动作 + NPC + 推进
      - 收束：心理 + 雾 + 收束语
      - 角色名收尾（触发 character freq）
    """
    for ch in chapters:
        if ch.status != "completed":
            continue
        if ch.final_content and len(ch.final_content) > 1500:
            continue  # 已有充足正文
        spec = CHAPTERS_BY_NO.get(ch.chapter_no)
        if spec is None:
            continue
        scenes = spec.get("scenes") or []
        random.seed(ch.chapter_no * 13 + 5)
        ch_title = ch.title or f"第{ch.chapter_no}章"
        pov_holder = (scenes[0].get("pov") if scenes else None) or "林雾"

        # 准备角色名 / 场景描述素材
        scene_summaries = [sc.get("summary", "") for sc in scenes]
        scene_titles = [sc.get("title", f"场景{i+1}") for i, sc in enumerate(scenes)]
        moods = [sc.get("mood", "内敛") for sc in scenes]
        n_scenes = len(scenes)

        # 写一个完整章节的真实散文
        paragraphs = []
        paragraphs.append(f"　　{ch_title}")
        paragraphs.append("")

        # ① 开场：人物 + 环境刻画
        paragraphs.append(_opening_phrase(ch.chapter_no, pov_holder, ch.objective))
        paragraphs.append(_opening_psych(pov_holder, moods[0] if moods else "内敛"))
        paragraphs.append(_opening_sense())
        paragraphs.append("")

        # ② 每个 scene 块
        for idx, (st, ss, md) in enumerate(zip(scene_titles, scene_summaries, moods)):
            scene_pov = scenes[idx].get("pov") or pov_holder
            # 场景标题 + 概要 + setting
            paragraphs.append(
                f"　　{st}。{scene_pov}站在{_pick_setting(idx)}的阴影下，{ss}"
            )
            # 场景氛围延展（独立段落，扩字数）
            paragraphs.append(_scene_atmosphere(st, idx))
            # 感官描写
            paragraphs.append(_sense_beat(md, idx))
            # 心理描写
            paragraphs.append(_inner_psych(scene_pov, md, idx))
            # 动作推进
            paragraphs.append(_action_beat(idx, n_scenes))
            # NPC 互动
            paragraphs.append(_npc_beat(idx, n_scenes))
            # 对话/旁白延展（独立段落，扩字数）
            paragraphs.append(_dialogue_beat(idx, n_scenes))
            # 情节推进
            paragraphs.append(_progression_phrase(idx, n_scenes))
            paragraphs.append("")

        # ③ 章节收束：心理 + 雾 + 收束语
        paragraphs.append(_closing_phrase_ext(pov_holder, ch.chapter_no))
        paragraphs.append("　　雾还没散。")
        paragraphs.append("")
        paragraphs.append("　　—— 终 ——")

        # ④ 角色名收尾（触发 character freq）
        epilogue = (
            "　　本章出场角色：林雾、顾沉、闻柯、白葵、裴衡。"
            "镜湖城的灰雾在审判署的汽笛声中愈发浓重，"
            "林雾与顾沉的对峙被闻柯与白葵看在眼里，"
            "而次官裴衡的阴影始终笼罩在档案司上空。"
            "下一章的钟声，将从第七城废墟的方向响起。"
        )
        paragraphs.append(epilogue)

        ch.final_content = "\n".join(paragraphs)
        # 同步 word_count（按中文字符 + 英文/数字）
        ch.word_count = len([c for c in ch.final_content if "\u4e00" <= c <= "\u9fff"]) + \
            len([c for c in ch.final_content if c.isascii() and c.isalnum()])
        db.commit()


def _ensure_chapter_versions(db, project_id: int, chapters):
    """为已完成的章节补一份 ChapterVersion（含可解析的一致性报告），用于驾驶舱雷达图。"""
    for ch in chapters:
        if ch.status != "completed":
            continue
        existing = db.scalar(
            select(ChapterVersion).where(ChapterVersion.chapter_id == ch.id).limit(1)
        )
        if existing is not None:
            continue
        # 模拟 AI 评分 75-95 区间
        random.seed(ch.chapter_no * 7 + 3)
        scores = {
            "character": random.randint(78, 92),
            "plot": random.randint(72, 90),
            "world": random.randint(76, 94),
            "pacing": random.randint(70, 88),
            "style": random.randint(80, 95),
        }
        report = (
            f"角色一致性: {scores['character']} 分\n"
            f"剧情连贯性: {scores['plot']} 分\n"
            f"世界设定: {scores['world']} 分\n"
            f"节奏控制: {scores['pacing']} 分\n"
            f"风格统一: {scores['style']} 分\n"
        )
        version = ChapterVersion(
            project_id=project_id,
            chapter_id=ch.id,
            version_no=1,
            operation_type="draft_generation",
            instruction=None,
            consistency_report=report,
            content=ch.final_content or (ch.summary or ""),
            summary=ch.summary,
            selected_model="demo-mock",
        )
        db.add(version)
    db.commit()


def _ensure_ai_tasks(db, project_id: int, chapters):
    """为已完成的章节创建 task + step + log，便于驾驶舱展示。"""
    now = datetime.now(timezone.utc)
    completed_chapters = [c for c in chapters if c.status == "completed"]
    if not completed_chapters:
        return

    # 只在没有相关 task 时插入
    existing_task_titles = {
        t.title for t in db.scalars(select(AITask).where(AITask.project_id == project_id))
    }
    tasks_created: list[AITask] = []
    for idx, ch in enumerate(completed_chapters):
        title = f"AI 自动创作 · 第 {ch.chapter_no} 章《{ch.title}》"
        if title in existing_task_titles:
            continue
        started = now - timedelta(minutes=random.randint(60, 180))
        finished = started + timedelta(seconds=random.randint(60, 180))
        task = AITask(
            project_id=project_id,
            chapter_id=ch.id,
            task_type="novel_chapter_generation",
            module_type="chapter_writer",
            title=title,
            input_payload=json.dumps({
                "chapter_no": ch.chapter_no,
                "topic": ch.title,
                "word_target": ch.word_count,
            }, ensure_ascii=False),
            plan_text=f"1. 解析章节大纲\n2. 抽取 3-7 个场景\n3. 逐场景生成\n4. 一致性校验",
            reasoning_trace="通过 react_state 循环：think -> act -> observe",
            tool_trace=json.dumps([
                {"tool": "llm_generate", "latency_ms": 4200},
                {"tool": "query_neo4j", "latency_ms": 360},
                {"tool": "consistency_check", "latency_ms": 800},
            ], ensure_ascii=False),
            output_payload=json.dumps({
                "novel_title": "蒸汽审判者",
                "chapters_count": ch.chapter_no,
                "target_chapters": 15,
                "total_words": ch.word_count,
            }, ensure_ascii=False),
            status="completed",
            mode="auto",
            started_at=started,
            finished_at=finished,
            created_at=started,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        tasks_created.append(task)

    # 给所有 task 补 steps + logs
    for task in list(db.scalars(select(AITask).where(AITask.project_id == project_id, AITask.status == "completed"))):
        if db.scalar(select(TaskStep).where(TaskStep.task_id == task.id).limit(1)):
            continue
        steps_spec = [
            (1, "think", "analyze", "analyze", "分析章节大纲与剧情线", 1200),
            (2, "act", "act", "llm", "调用 LLM 生成章节草稿", 4200),
            (3, "observe", "observe", "consistency", "一致性检查", 800),
            (4, "act", "act", "graph", "同步图谱与角色状态", 360),
            (5, "observe", "observe", "file", "写入数据库与场景拆分", 240),
        ]
        for step_no, name, step_type, react_state, summary, latency_ms in steps_spec:
            step_started = task.started_at + timedelta(seconds=sum(s[5] for s in steps_spec[: step_no - 1]) / 1000)
            step_finished = step_started + timedelta(milliseconds=latency_ms)
            step = TaskStep(
                task_id=task.id,
                step_no=step_no,
                step_name=summary,
                step_type=step_type,
                react_state=react_state,
                tool_name=react_state,
                input_payload=json.dumps({"step": step_no, "tool": react_state}, ensure_ascii=False),
                output_payload=json.dumps({"ok": True, "latency_ms": latency_ms}, ensure_ascii=False),
                status="completed",
                started_at=step_started,
                finished_at=step_finished,
            )
            db.add(step)
            db.add(TaskLog(
                task_id=task.id,
                step_no=step_no,
                log_type=react_state,
                message=summary,
                payload=json.dumps({"latency_ms": latency_ms}, ensure_ascii=False),
                created_at=step_finished,
            ))
        db.commit()


def _pick_setting(idx: int) -> str:
    return ["禁律长廊", "第七城废墟的入口", "档案司第七司", "禁律院的廊桥", "镜湖城的高架桥"][idx % 5]


def _progression_phrase(idx: int, total: int) -> str:
    if idx == 0:
        return "　　档案室外的风压比往常更重，似乎在暗示雾区昨夜又有了新异动。"
    if idx == total - 1:
        return "　　所有的线索都聚向了同一个方向——第七城废墟的深处。"
    return f"　　档案柜的锁舌在寂静中发出低沉的金属摩擦声，像是某种回应。"


def _closing_phrase(chapter_no: int) -> str:
    phrases = [
        "在禁律被遵守的地方，秘密比雾更耐久。",
        "档案一旦被记录，就再也不会消失。",
        "听不见的雾，才是最危险的。",
        "灰雾从不撒谎，它只是把真相藏得更深。",
        "禁律锁记住了一切，也包括你忘了的部分。",
        "档案司的走廊很长，足以让一个人忘掉自己为什么进来。",
        "每一次雾散开，都只是换了一种迷障。",
    ]
    return phrases[chapter_no % len(phrases)]


# ----------------------------------------------------------------------------
# 章节正文扩写 helpers（每章 ≥ 1500 字）
# ----------------------------------------------------------------------------


def _opening_phrase(chapter_no: int, pov: str, objective: str | None) -> str:
    """开篇：人物 + 时代背景 + 行动起势。"""
    # 清理 objective 末尾标点，避免重复。
    obj = (objective or "").rstrip("。，、！？；：")
    obj = obj or None
    anchors = [
        f"那是{obj or '镜湖城还笼罩在旧世纪的灰雾里'}的一个清晨，"
        f"城北的蒸汽钟比城东早响半刻。{pov}从档案司第七司那间仅有半扇窗的宿舍里起身，"
        f"动作利落地披上深灰色长袍，把昨夜整理到一半的草稿塞进内袋。",
        f"镜湖城第七城区的夜雨刚停，{obj or '禁律院的告示牌在街角闪着湿漉漉的铜光'}。"
        f"{pov}靠在禁律长廊的扶栏上，听见自己的心跳比档案柜的钟摆还快两拍。",
        f"{obj or '审判署在昨夜发布了新的禁入区名单'}，{pov}把名单从袖口抽出来又叠回去。"
        f"第七城的灰雾沿着高架桥漫下来，吞掉了她刚写到第三页的草稿。",
        f"档案司第七司的铜门在凌晨三时被推开，{obj or '那是她连续第三夜没有合眼'}。"
        f"{pov}把油灯调到最暗，借着灯芯的微光把昨夜读到的那半句残页重新写进袖口。",
        f"街角的汽笛刚响过第一声，{obj or '雾区又传来了新的异动报告'}。"
        f"{pov}从禁律长廊的阴影里走出来，步子比平常更沉，"
        f"像是要把昨夜没说完的那句话也一起带走。",
    ]
    anchor = anchors[chapter_no % len(anchors)]
    return (
        f"　　{anchor}她向铜镜瞥了一眼，镜里的脸比往日更白些，颧骨下方浮着薄薄一层青灰。"
        f"炉心的蒸汽在窗外被风吹散，结成一层淡淡的霜。"
        f"她下意识地压了压袖口——那里藏着一份昨夜誊写的旧档副本，封皮上写着导师贺无声的名字。"
    )


def _opening_psych(pov: str, mood: str) -> str:
    """开篇后第二段：心理/内心。"""
    beats = [
        f"　　{pov}知道这一天不会和别的日子有什么不同：禁律院的巡察钟会敲到第七响，"
        f"档案司的封条会再添一道，灰雾会在傍晚前彻底封住第七城的入口。"
        f"但她仍然把脚步放得很轻，仿佛这样就能把昨夜那句未完的证词再挽留一瞬。",
        f"　　{pov}在禁律长廊的尽头停住，回头望了一眼第七司的铜门。"
        f"她想起导师贺无声在失踪前对她说的最后一句——「别让档案替你决定害怕什么」。"
        f"那句话在胸口压了三天，至今没有散开。",
        f"　　{pov}把手按在腰间的禁律锁上，"
        f"锁的温度比平时低半度，像是里面藏着的档案刚刚被谁翻过。"
        f"她没有立刻把它打开，而是沿着廊道慢慢走向档案司的深处。",
    ]
    return beats[hash(mood) % len(beats)]


def _opening_sense() -> str:
    """开篇后第三段：环境感官（开篇氛围统一收束）。"""
    return (
        "　　湿冷的风沿着档案司的石阶漫上来，携带着纸页、焦油与禁律院才会有的锈味。"
        "档案司的灯在这一刻全数灭了半秒，灯芯里爆出极细的火星，又被风迅速压住。"
        "远处的蒸汽钟又开始敲第二轮，每一声都像在提醒她——"
        "雾里的某些东西，正以比汽笛更稳的频率靠近。"
    )


def _sense_beat(mood: str, idx: int) -> str:
    """每个 scene 块的感官描写（变体由 idx 驱动）。"""
    beats = [
        "　　空气中浮着一股淡得几乎闻不出的硝味，混着档案司特有的樟脑与铜锈，"
        "让人的鼻腔在第一口呼吸时就被收紧。",
        "　　禁律长廊另一头有人在低语，话语被石壁弹回来就成了听不清的嗡鸣，"
        "像是有另一组钟摆在石缝里悄悄运行。",
        "　　窗外的汽笛又响了一轮，汽笛里的金属共振让胸腔也跟着微微发麻，"
        "连袖口里的草稿都跟着震了一下。",
        "　　档案司的灯在这一刻全数灭了半秒，灯芯里爆出极细的火星，"
        "火星落在禁律锁的锁舌上，被立刻吸走。",
        "　　地下管道里传来的不只是蒸汽，"
        "还有一种被称作「旧语法」的细响，震得她脚下的铁栅跟着轻轻打颤。",
        "　　禁律院的廊桥上方悬着一盏红铜灯，"
        "灯光在灰雾里被稀释成极薄的一层，"
        "落下来的时候像是要给桥下的每一块砖都上色。",
    ]
    return beats[idx % len(beats)]


def _inner_psych(pov: str, mood: str, idx: int) -> str:
    """每个 scene 块的心理描写（变体由 idx 驱动，避免重复）。"""
    beats = [
        f"　　{pov}下意识地压低呼吸，让心跳的频率合上档案室外的钟摆，"
        f"仿佛这样就能把接下来要发生的事再延后半秒。",
        f"　　{pov}告诉自己不要回头，但肩胛骨却绷得像禁律锁的锁舌，"
        f"在皮肤底下轻轻发出金属的颤音。",
        f"　　{pov}的手在封条边缘停顿了一瞬——"
        f"封条上的墨迹仿佛比上一次更湿，写下的字似乎在纸面上被重新写过一次。",
        f"　　{pov}压住指节间细微的颤抖，把注意力全部集中在禁律锁的指针上，"
        f"指针在「三十二」与「三十三」之间犹豫了一瞬才停下。",
        f"　　{pov}感到一种陌生的热度沿着手腕向肩膀爬升，"
        f"她没敢低头去看，但袖口里的草稿已经跟着手腕上的烙印一起发烫。",
        f"　　{pov}把卷宗翻过第二页时，听见自己耳朵里嗡嗡作响，"
        f"像是有另一组人在她头顶的石板上方低声核对名单。",
        f"　　{pov}抬眼注视着对方的袖口，那里有执法司惯有的焰纹刺绣，"
        f"刺绣的颜色在灰雾里显得格外刺目。",
        f"　　{pov}把档案压得更紧，仿佛这样就能让话语的重量从自己身上卸下，"
        f"把责任整个推回到禁律院那一端。",
        f"　　{pov}在脑子里排演了三套措辞，最终只挑出最平实的那一句，"
        f"——她知道一句错话就足以让档案柜上多出一道封条。",
    ]
    return beats[idx % len(beats)]


def _action_beat(idx: int, total: int) -> str:
    """每个 scene 块的动作/情节推进。"""
    beats = [
        "　　她俯身去看那半张纸，纸背的旧语法符号正以极慢的速度向边缘扩散，"
        "像是要替纸面上的字另起一行。",
        "　　她从内袋取出昨夜自制的炭笔，在卷宗空白处记下「三十二」三个字，"
        "写完又用指腹抹去，纸面却仍留着一道极浅的灰痕。",
        "　　她用指节敲了敲档案柜的侧板，那面金属应声发出极轻的回响——"
        "禁律锁下层是空的，封条却几乎是新贴的。",
        "　　她把灯芯向左推了半寸，火苗骤低，禁律锁的影子被拉得很长，"
        "像是要替她把灰雾再撕开一道口子。",
        "　　她俯身去看那半张纸，纸背的旧语法符号正以极慢的速度向边缘扩散，"
        "像是要替纸面上的字另起一行——她把纸重新按回档案袋，封口的那一刹那，"
        "听见自己手腕上的烙印跟着「嗡」了一声。",
    ]
    return beats[idx % min(5, total + 1 if total > 0 else 1)] if total > 0 else beats[0]


def _npc_beat(idx: int, total: int) -> str:
    """每个 scene 块引入一个 NPC 互动（取代原 if/elif 链）。"""
    beats = [
        "　　顾沉的声音从廊道尽头传过来，夹杂着执法司惯有的冷："
        "「你昨晚又去了雾区。」他不是在问。",
        "　　闻柯在档案室门外吹了声口哨，"
        "那是他在提醒所有人，第七城废墟的汽笛刚响过第三遍。",
        "　　白葵把一张封条贴到档案柜上，"
        "封条上的字是用禁律墨写的，被水浸过会显出第二层颜色。",
        "　　裴衡在拐角处站了一会儿。"
        "他没有说话，只是把一卷档案从袖口取下，又放回原处。",
        "　　顾沉在廊桥那端把令牌收回袖中，"
        "但目光仍停在林雾的袖口——那里藏着的草稿似乎比档案柜更沉。",
    ]
    return beats[idx % min(len(beats), max(1, total))]


def _scene_atmosphere(st: str, idx: int) -> str:
    """每个 scene 块的氛围延展段落（让场景更立体）。"""
    beats = [
        "　　街灯在雾里只亮出半边，"
        "另一半被吸进档案司的石缝里，让整条廊道看起来像被谁对折过一次。",
        "　　旧管道的接口处渗出一丝极淡的白汽，"
        "白汽碰到地面的积水便凝成细小的铁屑，被她一脚踩出细碎的声响。",
        "　　廊桥的红铜灯被她甩在身后，"
        "她听见禁律院的巡察钟正从远端一响一响地逼近，"
        "每响一下，石壁上的水痕就跟着抖一次。",
        "　　档案司的地板在她脚底下咯吱作响，"
        "那是昨夜才换上的松木条；木条在灰雾里散出一股新伐的松脂气，"
        "与她记忆里那间旧档案室的气味完全不一样。",
        "　　蒸汽管道在头顶低低鸣响，"
        "她抬头看时，金属管的焊缝处有一处正在微微渗出蒸汽，"
        "蒸汽被汽笛声压着，几乎凝成可见的水汽。",
        "　　禁律长廊的尽头站着一名穿灰袍的巡察员，"
        "他没看她的档案，只是把胸前的令牌向她那一侧抬了抬，"
        "表示允许她通过。",
    ]
    return beats[idx % len(beats)]


def _dialogue_beat(idx: int, total: int) -> str:
    """每个 scene 块的对白/旁白延展段落。"""
    beats = [
        "　　「你知不知道，」她在心里默念，"
        "「导师失联的那一晚，他根本不该在档案司。」——她没说出口，"
        "只把档案袋往袖口里又按了按。",
        "　　炉心那边传来一声极长的汽笛，汽笛的尾音从管道口绕了一圈，"
        "贴着她的耳根发梢慢慢退开。她想起导师说过的那句："
        "「管道的回声不会撒谎。」",
        "　　「封条没干。」她低声对自己说，"
        "「说明贴封条的人在最近一炷香内还在这间档案室。」"
        "——这一句话她在心里翻了三遍，始终没有写进草稿。",
        "　　她盯着封条上的笔迹，笔迹里有一点点不易察觉的抖："
        "贴封条的人在那一刻，犹豫过。她在草稿的边角写下一行极小的字——"
        "「次官？」——然后用袖口把它抹平。",
        "　　顾沉从廊桥那端递过来一个眼神，"
        "那个眼神里没有放行，也没有阻拦，"
        "只是告诉她——禁律院会在天亮前再查一次。",
        "　　白葵在门口补了一句："
        "「禁律墨被水浸过会显字，你要不要先去看一眼水缸？」"
        "——她没答，但脚步已经朝水缸那一端偏过去。",
    ]
    n = max(1, min(len(beats), total + 1))
    return beats[idx % n]


def _closing_phrase_ext(pov: str, chapter_no: int) -> str:
    """收束：心理 + 雾 + 收束语。"""
    intros = [
        f"　　夜深时，{pov}合上档案柜，禁律锁的指针停在「三十二」上。"
        f"她在烛光下把自己的左手翻过来——手腕内侧那道旧语法的烙痕仍在微微发烫，"
        f"像是要回应她刚才读到的那半句残页。"
        f"她想起白葵说过的那句话：{_closing_phrase(chapter_no)}",
        f"　　凌晨四点，{pov}从档案司的铜门里走出，身后是第七司已经熄了半数的灯。"
        f"她在街角站定，把昨夜那半张残页重新折好放进袖口。"
        f"灰雾在钟楼下聚成一团，像是要替她把今天的事再藏一日。"
        f"她想起白葵说过的那句话：{_closing_phrase(chapter_no)}",
        f"　　钟楼敲过第七响时，{pov}把巡察记录从档案柜里抽出，"
        f"用禁律院的封条在最后一页贴上了自己的代号。"
        f"炉心的蒸汽在窗外散成雾，雾在窗沿结成霜，霜在封条上融成一道极细的水痕。"
        f"她想起白葵说过的那句话：{_closing_phrase(chapter_no)}",
        f"　　{pov}在禁律长廊的尽头站了很久。"
        f"廊道里的灯一盏接一盏地熄下去，只有她袖口里的半张残页还带着微弱的热度。"
        f"她低头看了一眼那道烙印，烙印的颜色比早晨更深一些。"
        f"她想起白葵说过的那句话：{_closing_phrase(chapter_no)}",
        f"　　破晓前，{pov}在档案司的石阶上把那份誊写好的副本重新塞进内袋。"
        f"她抬头看了一眼天色——灰雾比往日更厚，汽笛的金属味比往日更浓。"
        f"她知道禁律院的巡察钟会在一炷香后敲响。"
        f"她想起白葵说过的那句话：{_closing_phrase(chapter_no)}",
    ]
    return intros[chapter_no % len(intros)]


def main() -> None:
    random.seed(42)
    create_db_and_tables()
    db = SessionLocal()
    try:
        project = _ensure_project(db)
        print(f"[seed] project: id={project.id}, name={project.name}")
        _ensure_characters(db, project.id)
        chars = {c.name: c for c in db.scalars(select(Character).where(Character.project_id == project.id))}
        _ensure_relationships(db, project.id, chars)
        _ensure_plot_lines(db, project.id)
        _ensure_chapters(db, project.id)
        chapters = list(db.scalars(select(Chapter).where(Chapter.project_id == project.id).order_by(Chapter.chapter_no)))
        _ensure_scene_plot_lines(db, project.id, chapters)
        _ensure_chapter_content(db, project.id, chapters)
        _ensure_chapter_versions(db, project.id, chapters)
        _ensure_ai_tasks(db, project.id, chapters)
        print(f"[seed] chapters: {len(chapters)}")
        print(f"[seed] characters: {len(chars)}")
        print(f"[seed] plot_lines: {db.scalar(select(PlotLine).where(PlotLine.project_id == project.id, PlotLine.plot_type == 'main').limit(1)) and 'yes' or 'no'}")
        print("[seed] done")
    finally:
        db.close()


if __name__ == "__main__":
    main()
