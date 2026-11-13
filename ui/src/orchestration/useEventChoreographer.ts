import { useState, useEffect, useRef, useCallback } from 'react';
import { EventItem } from '../api';

export type PlaybackMode = 'cinematic' | 'instant';

interface ChoreographerOptions {
  llmMode?: string; // 'real' | 'mock'
  isRealMode?: boolean;
  speed?: PlaybackMode;
  onComplete?: () => void;
}

export function useEventChoreographer(
  rawEvents: EventItem[],
  options: ChoreographerOptions = {}
) {
  const [choreographedEvents, setChoreographedEvents] = useState<EventItem[]>([]);
  const [playbackSpeed, setPlaybackSpeed] = useState<PlaybackMode>(options.speed || 'cinematic');
  const [isProcessing, setIsProcessing] = useState<boolean>(false);

  useEffect(() => {
    if (options.speed && options.speed !== playbackSpeed) {
      setPlaybackSpeed(options.speed);
    }
  }, [options.speed]);

  const queueRef = useRef<EventItem[]>([]);
  const processedKeysRef = useRef<Set<string>>(new Set());
  const timerRef = useRef<any>(null);
  const isInstant = playbackSpeed === 'instant';

  const isRealMode = options.isRealMode ?? (options.llmMode || '').trim() === 'real';

  // Generate deterministic event key for deduplication
  const getEventKey = (evt: EventItem, idx: number): string => {
    const p = evt.payload || {};
    const taskPart = p.task_id || p.simulation_id || p.conflict_id || '';
    const attemptPart = p.attempt !== undefined ? `_att${p.attempt}` : '';
    const modePart = p.mode || '';
    return `${evt.ts}_${evt.type}_${evt.agent}_${taskPart}_${attemptPart}_${modePart}_${idx}`;
  };

  // Push new incoming SSE events into the queue
  useEffect(() => {
    const newItems: EventItem[] = [];
    rawEvents.forEach((evt, idx) => {
      const key = getEventKey(evt, idx);
      if (!processedKeysRef.current.has(key)) {
        processedKeysRef.current.add(key);
        newItems.push(evt);
      }
    });

    if (newItems.length > 0) {
      queueRef.current.push(...newItems);
      scheduleNext();
    }
  }, [rawEvents]);

  // Compute dwell time based on event type and mode
  const getDwellTime = useCallback((evt: EventItem, queueLength: number): number => {
    if (isInstant) return 0;

    // High priority events (Chaos injection and failure recovery) execute immediately
    if (
      evt.type === 'failure_injected' ||
      evt.type === 'agent_failed' ||
      evt.type.startsWith('recovery_') ||
      evt.type === 'agent_healed'
    ) {
      return 100;
    }

    // In real LLM mode, latency is already natural; only coalesce rapid bursts
    if (isRealMode) {
      if (queueLength > 5) return 80;
      if (evt.type === 'finding_posted') return 250;
      return 150;
    }

    // Deterministic pacing offsets in mock mode
    const agent = (evt.agent || '').toLowerCase();
    const agentDelayMap: Record<string, number> = {
      cfo: 400,
      growth: 700,
      cto: 1000,
      customer: 1300,
      product: 1600,
      skeptic: 800,
      supervisor: 500
    };

    switch (evt.type) {
      case 'agent_started': {
        const offset = agentDelayMap[agent] ?? 500;
        return offset;
      }
      case 'finding_posted': {
        if (evt.payload?.type === 'rebuttal') return 1400;
        return 1800; // Specialist thinking and typewriter window
      }
      case 'conflict_detected':
        return 1200;
      case 'simulation_run':
        return 120; // 18 runs * 120ms = ~2.1 seconds to fill matrix
      case 'verification_passed':
      case 'verification_failed':
        return 500;
      case 'report_ready':
        return 600;
      default:
        return 350;
    }
  }, [isInstant, isRealMode]);

  // Worker loop to pop events and advance the choreographed timeline
  const scheduleNext = useCallback(() => {
    if (timerRef.current) return;
    if (queueRef.current.length === 0) {
      setIsProcessing(false);
      return;
    }

    setIsProcessing(true);
    const nextEvt = queueRef.current[0];
    const delay = getDwellTime(nextEvt, queueRef.current.length);

    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      const popped = queueRef.current.shift();
      if (popped) {
        setChoreographedEvents((prev) => [...prev, popped]);
      }
      scheduleNext();
    }, delay);
  }, [getDwellTime]);

  // Skip queue: flush everything to 0ms immediately
  const skipToReport = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    const remaining = [...queueRef.current];
    queueRef.current = [];
    if (remaining.length > 0) {
      setChoreographedEvents((prev) => [...prev, ...remaining]);
    }
    setIsProcessing(false);
  }, []);

  // Flush when toggled to instant
  useEffect(() => {
    if (isInstant && queueRef.current.length > 0) {
      skipToReport();
    }
  }, [isInstant, skipToReport]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  // Reset when starting a completely fresh run
  const resetChoreographer = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    queueRef.current = [];
    processedKeysRef.current.clear();
    setChoreographedEvents([]);
    setIsProcessing(false);
  }, []);

  return {
    choreographedEvents,
    pendingCount: queueRef.current.length,
    playbackSpeed,
    setPlaybackSpeed,
    skipToReport,
    isProcessing,
    reset: resetChoreographer,
    resetChoreographer
  };
}
