import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Bot, User, Cpu } from 'lucide-react';
import './AgentChat.css';

type MessageBubbleProps = {
  role: 'user' | 'assistant' | 'tool';
  content: string;
  timestamp?: string;
  isStreaming?: boolean;
};

export function MessageBubble({ role, content, timestamp, isStreaming }: MessageBubbleProps) {
  const Icon = role === 'user' ? User : role === 'assistant' ? Bot : Cpu;
  return (
    <div className={`message-bubble message-bubble-${role}`}>
      <div className="message-bubble-avatar">
        <Icon size={14} />
      </div>
      <div className="message-bubble-body">
        <div className="message-bubble-content">
          {role === 'user' ? (
            <p>{content}</p>
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ node, inline, className, children, ...props }: any) {
                  const match = /language-(\w+)/.exec(className || '');
                  return !inline && match ? (
                    <SyntaxHighlighter style={vscDarkPlus as any} language={match[1]} PreTag="div" {...props}>
                      {String(children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  ) : (
                    <code className={className} {...props}>{children}</code>
                  );
                },
              }}
            >
              {content}
            </ReactMarkdown>
          )}
          {isStreaming && <span className="message-bubble-cursor">▍</span>}
        </div>
        {timestamp && <div className="message-bubble-time">{new Date(timestamp).toLocaleTimeString('zh-CN')}</div>}
      </div>
    </div>
  );
}
