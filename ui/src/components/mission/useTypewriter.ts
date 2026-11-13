import { useState, useEffect } from 'react';

/**
 * Typewriter effect for streaming text believably.
 * If instant is true, returns full text immediately.
 */
export function useTypewriter(fullText: string = '', speedMs: number = 14, instant: boolean = false): string {
  const [displayedLength, setDisplayedLength] = useState(instant ? fullText.length : 0);

  useEffect(() => {
    if (instant || !fullText) {
      setDisplayedLength(fullText.length);
      return;
    }

    setDisplayedLength(0);
    const interval = setInterval(() => {
      setDisplayedLength((prev) => {
        const next = prev + 3; // jump 3 chars per tick for smooth natural velocity
        if (next >= fullText.length) {
          clearInterval(interval);
          return fullText.length;
        }
        return next;
      });
    }, speedMs);

    return () => clearInterval(interval);
  }, [fullText, speedMs, instant]);

  return fullText.slice(0, displayedLength);
}

