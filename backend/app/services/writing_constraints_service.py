"""Writing Constraints Service — 把项目级"超参数"真正注入到 LLM 创作链路。

此前的问题：``NovelProject`` 存了 ``writing_style`` / ``tone`` / ``genre`` /
``theme`` / ``target_audience``，章节也有 ``word_target``，但这些约束从来没有
被拼进任何生成 prompt，导致 AI "想怎么写就怎么写"——既不按字数，也不按风格，
还容易跑题。

本模块提供三件事：

1. ``count_words``：中英文混排友好的"字数"统计（CJK 按字计，拉丁词按词计）。
2. ``load_project_constraints``：从 DB 读出项目级约束，归一成一个 dataclass。
3. ``build_constraint_block`` / ``build_word_budget_line``：把约束渲染成一段
   明确的中文指令，供各创作 service 直接拼进 user_prompt。

设计原则：**纯函数 + 无副作用**，方便单测直接断言"prompt 里确实带上了
字数 / 风格 / 题材约束"。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.project import NovelProject


# 一个 CJK 表意文字 / 假名 / 谚文音节 算 1 个"字"
_CJK_RE = re.compile(
    r"[㐀-䶿一-鿿豈-﫿぀-ヿ가-힯]"
)
# 连续的拉丁/数字串算 1 个"词"
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\-]*")


def count_words(text: str | None) -> int:
    """统计"字数"：CJK 字符按字计，拉丁/数字串按词计。

    例：``"你好 world 123"`` → 2(你好) + 1(world) + 1(123) = 4。

    之所以不用 ``len(text)``：原实现把整段正文长度（含空格、标点、换行）
    当字数，中文还算得过去，但英文严重偏大，而且无法和"目标字数"对齐，
    更没法做"还差多少字"的反馈。
    """
    if not text:
        return 0
    cjk = len(_CJK_RE.findall(text))
    # 把 CJK 去掉后再数拉丁词，避免重复统计
    latin_only = _CJK_RE.sub(" ", text)
    words = len(_WORD_RE.findall(latin_only))
    return cjk + words


@dataclass(frozen=True)
class ProjectConstraints:
    """项目级创作约束（已归一，字段缺省时给出合理兜底）。"""

    project_id: int
    genre: str | None
    theme: str | None
    writing_style: str | None
    tone: str | None
    target_audience: str | None
    language: str
    target_chapters: int | None
    min_words_per_chapter: int
    max_words_per_chapter: int

    @property
    def word_target(self) -> int:
        """单章字数目标：取区间中点（向上取整到百位更自然）。"""
        mid = (self.min_words_per_chapter + self.max_words_per_chapter) // 2
        return max(self.min_words_per_chapter, mid)

    def style_hint(self) -> str:
        """给没有显式 style_hint 的调用方一个由项目约束推导的默认风格提示。"""
        parts: list[str] = []
        if self.writing_style:
            parts.append(self.writing_style)
        if self.tone:
            parts.append(f"基调{self.tone}")
        if self.genre:
            parts.append(self.genre)
        if not parts:
            return "节奏紧凑、画面感强、情绪有张力"
        return "、".join(parts)


# 字数兜底（找不到项目或字段为空时使用）
_DEFAULT_MIN_WORDS = 2000
_DEFAULT_MAX_WORDS = 4000
_DEFAULT_LANGUAGE = "zh-CN"

_LANGUAGE_LABELS = {
    "zh-CN": "简体中文",
    "zh": "中文",
    "en-US": "English",
    "en": "English",
}


def _clamp_word_range(min_words: int | None, max_words: int | None) -> tuple[int, int]:
    lo = min_words if (min_words and min_words > 0) else _DEFAULT_MIN_WORDS
    hi = max_words if (max_words and max_words > 0) else _DEFAULT_MAX_WORDS
    # 容错：min 比 max 大时交换；区间过窄时给一点余量
    if lo > hi:
        lo, hi = hi, lo
    lo = max(200, lo)
    hi = max(lo + 200, hi)
    return lo, hi


def load_project_constraints(db: Session, project_id: int) -> ProjectConstraints:
    """从 DB 读出项目约束。项目不存在时返回一份"全兜底"约束，绝不抛异常，
    保证创作链路在缺数据时仍能跑。"""
    project = db.get(NovelProject, project_id)
    if project is None:
        return ProjectConstraints(
            project_id=project_id,
            genre=None,
            theme=None,
            writing_style=None,
            tone=None,
            target_audience=None,
            language=_DEFAULT_LANGUAGE,
            target_chapters=None,
            min_words_per_chapter=_DEFAULT_MIN_WORDS,
            max_words_per_chapter=_DEFAULT_MAX_WORDS,
        )

    lo, hi = _clamp_word_range(
        getattr(project, "min_words_per_chapter", None),
        getattr(project, "max_words_per_chapter", None),
    )
    return ProjectConstraints(
        project_id=project_id,
        genre=project.genre,
        theme=project.theme,
        writing_style=project.writing_style,
        tone=project.tone,
        target_audience=project.target_audience,
        language=getattr(project, "language", None) or _DEFAULT_LANGUAGE,
        target_chapters=getattr(project, "target_chapters", None),
        min_words_per_chapter=lo,
        max_words_per_chapter=hi,
    )


def build_word_budget_line(
    constraints: ProjectConstraints,
    *,
    word_target: int | None = None,
    current_words: int | None = None,
) -> str:
    """渲染"字数预算"指令行，可选携带"当前已写字数"反馈。"""
    lo = constraints.min_words_per_chapter
    hi = constraints.max_words_per_chapter
    target = word_target or constraints.word_target
    target = max(lo, min(target, hi))
    line = (
        f"【字数要求】本章目标 {target} 字，必须落在 {lo}–{hi} 字区间内；"
        f"不足 {lo} 字视为不合格，请继续扩写情节与细节而非空泛堆砌。"
    )
    if current_words is not None:
        remaining = max(0, target - current_words)
        line += f" 当前已写约 {current_words} 字，还需约 {remaining} 字。"
    return line


def build_constraint_block(
    constraints: ProjectConstraints,
    *,
    word_target: int | None = None,
    current_words: int | None = None,
    include_word_budget: bool = True,
) -> str:
    """把项目约束渲染成一段明确的中文指令块，直接拼进 user_prompt。

    包含：语言、题材、风格、基调、受众、主题、字数预算、以及"不跑题"约束。
    """
    lang_label = _LANGUAGE_LABELS.get(constraints.language, constraints.language)
    lines: list[str] = ["【创作约束 · 必须严格遵守】"]
    lines.append(f"- 写作语言：{lang_label}")
    if constraints.genre:
        lines.append(f"- 题材类型：{constraints.genre}")
    if constraints.theme:
        lines.append(f"- 核心主题：{constraints.theme}（全篇围绕此主题展开，不得跑题）")
    if constraints.writing_style:
        lines.append(f"- 作品风格：{constraints.writing_style}（遣词、句式、叙事节奏均需贴合）")
    if constraints.tone:
        lines.append(f"- 情感基调：{constraints.tone}")
    if constraints.target_audience:
        lines.append(f"- 目标读者：{constraints.target_audience}（措辞与尺度需匹配该读者群）")

    if include_word_budget:
        lines.append(
            build_word_budget_line(
                constraints, word_target=word_target, current_words=current_words
            )
        )

    lines.append(
        "- 主题一致性：严禁偏离上述题材与主题；如剧情有发散倾向，须收束回主线。"
    )
    return "\n".join(lines)
