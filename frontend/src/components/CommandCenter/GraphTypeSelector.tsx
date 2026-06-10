import React from "react";

export type GraphType = "story_entity" | "character" | "plot_line" | "event" | "worldbook" | "chapter_plan" | "story_arc";

export interface GraphTypeOption {
  value: GraphType;
  label: string;
  description: string;
  /** 视角分类：用于前端排版时分组、提示用户当前是 AI 规范化产物还是手动维护资产。 */
  group: "ai_overview" | "ai_synth" | "manual";
}

export const GRAPH_TYPE_OPTIONS: GraphTypeOption[] = [
  {
    value: "story_entity",
    label: "实体关系图（综合）",
    description: "项目中所有资产的全景视图：角色、剧情、章节、世界观、关系等汇总展示。",
    group: "ai_overview",
  },
  {
    value: "character",
    label: "人物关系",
    description: "只展示 Character 节点及其 RELATED_TO 关系边；不含剧情、事件、世界观。",
    group: "manual",
  },
  {
    value: "plot_line",
    label: "情节脉络",
    description: "只展示 PlotLine 剧情线节点（含 DEVELOPS_INTO / INTERSECTS_WITH 等剧情线之间的关系）。",
    group: "manual",
  },
  {
    value: "story_arc",
    label: "故事脉络",
    description:
      "AI 自动规范化的故事结构：StoryArc 弧线 + StoryTheme 主题 + StoryEvent 关键事件，按生成时间排列。",
    group: "ai_synth",
  },
  {
    value: "event",
    label: "事件网络",
    description:
      "只展示 StoryEvent 事件节点 + CharacterEventParticipation 角色参与边，独立于故事脉络。",
    group: "manual",
  },
  {
    value: "worldbook",
    label: "世界观",
    description: "只展示 WorldbookEntry 世界观条目及其 INFLUENCES 关联边，不再混入事件 / 主题。",
    group: "manual",
  },
  {
    value: "chapter_plan",
    label: "章节结构",
    description: "章节节点之间的 PRECEDES 顺序关系 + HAS_PLAN 大纲设计关系。",
    group: "manual",
  },
];

export interface GraphTypeSelectorProps {
  value: GraphType;
  onChange: (value: GraphType) => void;
}

const GROUP_LABELS: Record<GraphTypeOption["group"], string> = {
  ai_overview: "—— 综合视图 ——",
  ai_synth: "—— AI 自动生成 ——",
  manual: "—— 手动维护资产 ——",
};

export function GraphTypeSelector({ value, onChange }: GraphTypeSelectorProps) {
  // 按 group 分组渲染 <optgroup>，让用户一眼分清「AI 合成」与「手动资产」。
  const grouped = GRAPH_TYPE_OPTIONS.reduce<Record<string, GraphTypeOption[]>>((acc, opt) => {
    (acc[opt.group] ||= []).push(opt);
    return acc;
  }, {});

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as GraphType)}
      className="cc-graph-selector"
      title={GRAPH_TYPE_OPTIONS.find((o) => o.value === value)?.description}
    >
      {(Object.keys(GROUP_LABELS) as Array<GraphTypeOption["group"]>).map((groupKey) => (
        <optgroup key={groupKey} label={GROUP_LABELS[groupKey]}>
          {(grouped[groupKey] || []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}
