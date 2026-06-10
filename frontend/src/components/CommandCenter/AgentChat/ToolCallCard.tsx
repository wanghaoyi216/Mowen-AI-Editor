import { useState } from 'react';
import { ChevronDown, ChevronUp, Search, Network, FileText, Cpu, BookOpen, Loader2, Check, X, AlertTriangle, Wrench } from 'lucide-react';
import './AgentChat.css';

type ToolCallCardProps = {
  toolName: string;
  args?: Record<string, any>;
  status: 'pending' | 'running' | 'success' | 'failed';
  duration?: number;  // ms
  result?: Record<string, any>;
  iconOverride?: any;
  errorMessage?: string;
};

const TOOL_ICONS: Record<string, any> = {
  search: Search,
  web_search: Search,
  query_neo4j: Network,
  build_knowledge_graph: Network,
  graph: Network,
  file: FileText,
  llm_generate: Cpu,
  chapter: BookOpen,
};

const TOOL_LABELS: Record<string, string> = {
  search: '搜索热点',
  web_search: '联网搜索',
  query_neo4j: '查询图谱',
  build_knowledge_graph: '构建故事图谱',
  user_directive: '采纳作者指示',
  runtime_control: '运行控制',
  file: '文件操作',
  llm_generate: 'LLM 生成',
  chapter: '章节生成',
  llm: 'LLM 调用',
  analyze: '语义分析',
  consistency: '一致性检查',
  graph: '图谱更新',
  write: '写入内容',
  system: '系统操作',
};

function getToolDisplay(toolName: string): { Icon: any; label: string } {
  const Icon = TOOL_ICONS[toolName] || Cpu;
  const label = TOOL_LABELS[toolName] || toolName;
  return { Icon, label };
}

function formatDuration(ms: number): string {
  if (!ms || ms <= 0) return '';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
  const m = Math.floor(ms / 60000);
  const s = Math.round((ms % 60000) / 1000);
  return `${m}m ${s}s`;
}

export function ToolCallCard({ toolName, args, status, duration, result, iconOverride, errorMessage }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false);
  const { Icon, label } = getToolDisplay(toolName);
  const ResolvedIcon = iconOverride ?? Icon;

  const statusClass = `tool-call-${status}`;
  const statusIcon = status === 'running' ? <Loader2 size={11} className="spin" /> :
                     status === 'success' ? <Check size={11} /> :
                     status === 'failed' ? <X size={11} /> : null;
  const safeDuration = duration ?? 0;

  return (
    <div className={`tool-call-card ${statusClass}`}>
      <button className="tool-call-header" onClick={() => setExpanded(!expanded)}>
        <div className="tool-call-header-left">
          <span className="tool-call-icon">
            <ResolvedIcon size={12} />
          </span>
          <span className="tool-call-name">{label}</span>
          {statusIcon}
          {status === 'failed' && errorMessage && (
            <span className="tool-call-error-hint">
              <AlertTriangle size={10} /> {errorMessage.slice(0, 40)}
            </span>
          )}
        </div>
        <div className="tool-call-header-right">
          {safeDuration > 0 && <span className="tool-call-duration">{formatDuration(safeDuration)}</span>}
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </div>
      </button>
      {expanded && (
        <div className="tool-call-details">
          {args && Object.keys(args).length > 0 && (
            <div className="tool-call-section">
              <div className="tool-call-section-title">输入参数</div>
              <pre>{JSON.stringify(args, null, 2)}</pre>
            </div>
          )}
          {result && Object.keys(result).length > 0 && (
            <div className="tool-call-section">
              <div className="tool-call-section-title">返回结果</div>
              <pre>{JSON.stringify(result, null, 2)}</pre>
            </div>
          )}
          {!args && !result && (
            <div className="tool-call-section">
              <div className="tool-call-section-title">无详细信息</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
