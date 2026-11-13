import React from 'react';

interface SystemNoticeProps {
  title?: string;
  content?: string;
  agent?: string;
  timestamp: string;
}

export const SystemNotice: React.FC<SystemNoticeProps> = ({
  title,
  content,
  agent,
  timestamp
}) => {
  const isChaos = title?.includes('⚡') || title?.toLowerCase().includes('fault') || title?.toLowerCase().includes('chaos');
  const isBackup = title?.includes('🛡️') || title?.toLowerCase().includes('backup');
  const isRetry = title?.toLowerCase().includes('recovery') || title?.toLowerCase().includes('retry');
  const isHealed = title?.toLowerCase().includes('healed');

  let bannerClass = 'bg-slate-900/90 border-slate-800 text-slate-300';
  let badgeClass = 'bg-slate-800 text-slate-300 border-slate-700';
  let badgeLabel = 'SYSTEM';

  if (isChaos) {
    bannerClass = 'bg-rose-950/20 border-rose-500/40 text-rose-200';
    badgeClass = 'bg-rose-500/20 text-rose-300 border-rose-500/40';
    badgeLabel = 'CHAOS INJECTION';
  } else if (isBackup) {
    bannerClass = 'bg-purple-950/20 border-purple-500/40 text-purple-200';
    badgeClass = 'bg-purple-500/20 text-purple-300 border-purple-500/40';
    badgeLabel = 'BACKUP SENTINEL';
  } else if (isRetry) {
    bannerClass = 'bg-amber-950/20 border-amber-500/40 text-amber-200';
    badgeClass = 'bg-amber-500/20 text-amber-300 border-amber-500/40';
    badgeLabel = 'RECOVERY PROTOCOL';
  } else if (isHealed) {
    bannerClass = 'bg-emerald-950/20 border-emerald-500/40 text-emerald-200';
    badgeClass = 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
    badgeLabel = 'HEALED & RESTORED';
  }

  return (
    <div className={`rounded-xl border p-3 font-mono text-xs shadow-sm ${bannerClass}`}>
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2">
          <span className={`text-[9px] px-2 py-0.5 rounded-full border uppercase tracking-wider font-semibold ${badgeClass}`}>
            {badgeLabel}
          </span>
          {title && <span className="font-semibold text-slate-200">{title}</span>}
        </div>
        <span className="text-[10px] text-slate-500">{timestamp}</span>
      </div>
      {content && (
        <div className="text-[11px] text-slate-300 leading-relaxed font-sans pl-1">
          {content}
        </div>
      )}
    </div>
  );
};

