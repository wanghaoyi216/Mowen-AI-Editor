import { useEffect, useRef, useState } from 'react';
import './AgentChat.css';

type StreamingOutputProps = {
  fullText: string;
  speed?: number; // ms per char
  onSkip?: () => void;
};

export function StreamingOutput({ fullText, speed = 30, onSkip }: StreamingOutputProps) {
  const [displayed, setDisplayed] = useState('');
  const [done, setDone] = useState(false);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!fullText) {
      setDisplayed('');
      setDone(false);
      return;
    }
    if (fullText === displayed) {
      setDone(true);
      return;
    }
    setDone(false);
    let i = displayed.length;
    timerRef.current = window.setInterval(() => {
      i += 1;
      setDisplayed(fullText.slice(0, i));
      if (i >= fullText.length) {
        if (timerRef.current) window.clearInterval(timerRef.current);
        setDone(true);
      }
    }, speed);
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fullText, speed]);

  return (
    <div className="streaming-output">
      <span className="streaming-output-text">{displayed}</span>
      {!done && <span className="streaming-output-cursor">▍</span>}
      {!done && onSkip && (
        <button className="streaming-output-skip" onClick={() => {
          setDisplayed(fullText);
          setDone(true);
          if (timerRef.current) window.clearInterval(timerRef.current);
          onSkip();
        }}>
          跳过
        </button>
      )}
    </div>
  );
}
