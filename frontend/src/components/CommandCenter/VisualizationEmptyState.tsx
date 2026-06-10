import React from 'react';

interface VisualizationEmptyStateProps {
  tabName: string;
  icon: React.ReactNode;
  description?: string;
}

const VisualizationEmptyState: React.FC<VisualizationEmptyStateProps> = ({
  tabName,
  icon,
  description = '待墨痕落定，方见云开',
}) => {
  return (
    <>
      <style>{`
        @keyframes fall1 {
          0% {
            transform: translateY(-20px) rotate(0deg);
            opacity: 0;
          }
          10% {
            opacity: 0.8;
          }
          90% {
            opacity: 0.6;
          }
          100% {
            transform: translateY(280px) rotate(360deg);
            opacity: 0;
          }
        }
        @keyframes fall2 {
          0% {
            transform: translateY(-30px) rotate(0deg);
            opacity: 0;
          }
          10% {
            opacity: 0.7;
          }
          90% {
            opacity: 0.5;
          }
          100% {
            transform: translateY(260px) rotate(-320deg);
            opacity: 0;
          }
        }
        @keyframes fall3 {
          0% {
            transform: translateY(-10px) rotate(0deg);
            opacity: 0;
          }
          15% {
            opacity: 0.9;
          }
          85% {
            opacity: 0.4;
          }
          100% {
            transform: translateY(300px) rotate(280deg);
            opacity: 0;
          }
        }
        @keyframes sway1 {
          0%, 100% {
            transform: translateX(0px);
          }
          50% {
            transform: translateX(15px);
          }
        }
        @keyframes sway2 {
          0%, 100% {
            transform: translateX(0px);
          }
          50% {
            transform: translateX(-12px);
          }
        }
        @keyframes brushFadeIn {
          0% {
            opacity: 0;
            transform: scale(0.95);
          }
          100% {
            opacity: 1;
            transform: scale(1);
          }
        }
        .ink-empty-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 48px 32px;
          background: rgba(255, 255, 255, 0.6);
          border: 1px dashed rgba(124, 58, 237, 0.2);
          border-radius: 16px;
          min-height: 400px;
          position: relative;
          overflow: hidden;
        }
        .ink-empty-illustration {
          width: 240px;
          height: 180px;
          position: relative;
          margin-bottom: 32px;
        }
        .ink-empty-content {
          text-align: center;
          animation: brushFadeIn 0.8s ease-out;
        }
        .ink-empty-icon {
          color: #6b3fa0;
          margin-bottom: 16px;
        }
        .ink-empty-title {
          font-size: 20px;
          font-weight: 600;
          color: #2d1b4a;
          margin: 0 0 12px 0;
        }
        .ink-empty-poem {
          font-size: 16px;
          color: #6b3fa0;
          margin: 0 0 8px 0;
          font-style: italic;
          letter-spacing: 2px;
        }
        .ink-empty-hint {
          font-size: 13px;
          color: rgba(107, 63, 160, 0.7);
          margin: 0;
        }
        .plum-blossom {
          position: absolute;
          width: 8px;
          height: 8px;
          background: #ec4899;
          border-radius: 50%;
          opacity: 0;
          filter: blur(0.5px);
        }
        .blossom-1 {
          left: 30px;
          animation: fall1 6s linear infinite;
        }
        .blossom-2 {
          left: 70px;
          animation: fall2 7s linear infinite;
          animation-delay: 1.2s;
        }
        .blossom-3 {
          left: 120px;
          animation: fall3 5.5s linear infinite;
          animation-delay: 2.5s;
        }
        .blossom-4 {
          left: 160px;
          animation: fall1 6.5s linear infinite;
          animation-delay: 0.8s;
        }
        .blossom-5 {
          left: 200px;
          animation: fall2 5s linear infinite;
          animation-delay: 3s;
        }
        .blossom-6 {
          left: 50px;
          animation: fall3 7.5s linear infinite;
          animation-delay: 4s;
        }
        .blossom-7 {
          left: 180px;
          animation: fall1 6.2s linear infinite;
          animation-delay: 2s;
        }
        .blossom-8 {
          left: 90px;
          animation: fall2 5.8s linear infinite;
          animation-delay: 3.5s;
        }
      `}</style>
      <div className="ink-empty-container">
        <div className="ink-empty-illustration">
          {/* 远山剪影 */}
          <svg
            viewBox="0 0 240 180"
            width="100%"
            height="100%"
            style={{ position: 'absolute', bottom: 0, left: 0 }}
          >
            {/* 背景山 - 最淡 */}
            <path
              d="M0 140 Q30 80 60 110 Q90 60 120 90 Q150 50 180 80 Q210 40 240 70 L240 180 L0 180 Z"
              fill="rgba(124, 58, 237, 0.05)"
            />
            {/* 中景山 */}
            <path
              d="M0 150 Q40 100 80 130 Q120 85 160 115 Q200 75 240 105 L240 180 L0 180 Z"
              fill="rgba(124, 58, 237, 0.08)"
            />
            {/* 近景山 */}
            <path
              d="M0 160 Q50 130 100 150 Q140 125 180 145 Q220 120 240 135 L240 180 L0 180 Z"
              fill="rgba(124, 58, 237, 0.1)"
            />
            {/* 毛笔笔画装饰 */}
            <path
              d="M100 60 Q120 55 140 65 Q160 70 180 60"
              stroke="#6b3fa0"
              strokeWidth="3"
              strokeLinecap="round"
              fill="none"
              opacity="0.4"
            />
            <path
              d="M110 75 Q130 70 150 78 Q170 82 185 75"
              stroke="#6b3fa0"
              strokeWidth="2"
              strokeLinecap="round"
              fill="none"
              opacity="0.3"
            />
          </svg>

          {/* 飘落梅花 */}
          <div className="plum-blossom blossom-1" style={{ top: '-10px' }} />
          <div className="plum-blossom blossom-2" style={{ top: '-15px' }} />
          <div className="plum-blossom blossom-3" style={{ top: '-5px' }} />
          <div className="plum-blossom blossom-4" style={{ top: '-20px' }} />
          <div className="plum-blossom blossom-5" style={{ top: '-8px' }} />
          <div className="plum-blossom blossom-6" style={{ top: '-12px' }} />
          <div className="plum-blossom blossom-7" style={{ top: '-18px' }} />
          <div className="plum-blossom blossom-8" style={{ top: '-14px' }} />

          {/* 中心毛笔图标 */}
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: '50%',
              transform: 'translate(-50%, -50%)',
              opacity: 0.15,
            }}
          >
            <svg width="80" height="80" viewBox="0 0 80 80">
              <path
                d="M40 5 Q45 20 42 35 Q40 50 38 65 Q37 72 35 78"
                stroke="#2d1b4a"
                strokeWidth="4"
                strokeLinecap="round"
                fill="none"
              />
              <path
                d="M40 5 Q35 20 38 35 Q40 50 42 65 Q43 72 45 78"
                stroke="#2d1b4a"
                strokeWidth="2"
                strokeLinecap="round"
                fill="none"
              />
            </svg>
          </div>
        </div>

        <div className="ink-empty-content">
          <div className="ink-empty-icon">{icon}</div>
          <h3 className="ink-empty-title">{tabName}</h3>
          <p className="ink-empty-poem">{description}</p>
          <p className="ink-empty-hint">AI 完成大纲后会自动生成可视化内容</p>
        </div>
      </div>
    </>
  );
};

export default VisualizationEmptyState;
