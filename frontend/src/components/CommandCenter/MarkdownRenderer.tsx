import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { colors } from './styles';

type MarkdownRendererProps = {
  content: string;
  maxHeight?: number;
};

const markdownStyles = `
  .md-renderer {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
    font-size: 14px;
    line-height: 1.8;
    color: ${colors.text};
    word-break: break-word;
  }
  .md-renderer h1 { font-size: 22px; font-weight: 700; color: #f1f5f9; margin: 16px 0 8px; border-bottom: 1px solid ${colors.border}; padding-bottom: 6px; }
  .md-renderer h2 { font-size: 19px; font-weight: 700; color: #e2e8f0; margin: 14px 0 6px; border-bottom: 1px solid ${colors.border}; padding-bottom: 4px; }
  .md-renderer h3 { font-size: 16px; font-weight: 600; color: #cbd5e1; margin: 12px 0 4px; }
  .md-renderer h4 { font-size: 15px; font-weight: 600; color: #94a3b8; margin: 10px 0 4px; }
  .md-renderer h5, .md-renderer h6 { font-size: 14px; font-weight: 600; color: #94a3b8; margin: 8px 0 4px; }
  .md-renderer p { margin: 6px 0; }
  .md-renderer a { color: #60a5fa; text-decoration: none; }
  .md-renderer a:hover { text-decoration: underline; }
  .md-renderer strong { color: #f1f5f9; font-weight: 600; }
  .md-renderer em { color: #cbd5e1; }
  .md-renderer ul, .md-renderer ol { margin: 6px 0; padding-left: 24px; }
  .md-renderer li { margin: 2px 0; }
  .md-renderer li::marker { color: ${colors.textSecondary}; }
  .md-renderer blockquote {
    border-left: 3px solid ${colors.accent};
    margin: 8px 0;
    padding: 4px 12px;
    color: ${colors.textSecondary};
    background: rgba(59, 130, 246, 0.06);
    border-radius: 0 4px 4px 0;
  }
  .md-renderer code {
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 13px;
    background: #1e293b;
    padding: 2px 6px;
    border-radius: 3px;
    color: #e2e8f0;
  }
  .md-renderer pre {
    background: #0d1117;
    border: 1px solid ${colors.border};
    border-radius: 6px;
    padding: 12px;
    overflow-x: auto;
    margin: 8px 0;
  }
  .md-renderer pre code {
    background: transparent;
    padding: 0;
    font-size: 13px;
    line-height: 1.6;
  }
  .md-renderer table {
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0;
    font-size: 13px;
  }
  .md-renderer th {
    background: #1e293b;
    border: 1px solid ${colors.border};
    padding: 8px 12px;
    text-align: left;
    font-weight: 600;
    color: #f1f5f9;
  }
  .md-renderer td {
    border: 1px solid ${colors.border};
    padding: 8px 12px;
    color: ${colors.text};
  }
  .md-renderer tr:nth-child(even) td {
    background: rgba(30, 41, 59, 0.5);
  }
  .md-renderer tr:nth-child(odd) td {
    background: transparent;
  }
  .md-renderer hr {
    border: none;
    border-top: 1px solid ${colors.border};
    margin: 12px 0;
  }
  .md-renderer img {
    max-width: 100%;
    border-radius: 4px;
  }
`;

export function MarkdownRenderer({ content, maxHeight = 400 }: MarkdownRendererProps) {
  if (!content) {
    return <div style={{ fontSize: 12, color: colors.textSecondary }}>无内容</div>;
  }

  return (
    <>
      <style>{markdownStyles}</style>
      <div
        className="md-renderer"
        style={{
          maxHeight,
          overflow: 'auto',
          background: '#111827',
          border: `1px solid ${colors.border}`,
          borderRadius: 6,
          padding: 12,
        }}
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    </>
  );
}
