import React, { useEffect, useState } from 'react';
import { fetchCompanyGraph } from '../api';

export const CompanyGraphView: React.FC = () => {
  const [graphData, setGraphData] = useState<{ nodes: any[]; edges: any[] } | null>(null);

  useEffect(() => {
    fetchCompanyGraph().then(setGraphData).catch(() => {});
  }, []);

  if (!graphData) {
    return <div className="p-8 text-center text-slate-500">Loading company dependency graph...</div>;
  }

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-white">Company Intelligence Graph</h2>
            <span className="px-2.5 py-0.5 text-xs font-semibold uppercase bg-brand-500/10 text-brand-400 border border-brand-500/20 rounded-full">
              System Topology
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">Dependency graph mapping revenue drivers, product plans, and operational cost nodes</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {graphData.nodes.map((node) => {
          let badgeColor = 'bg-slate-800 text-slate-300';
          if (node.type === 'financial') badgeColor = 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
          if (node.type === 'plan') badgeColor = 'bg-brand-500/20 text-brand-400 border border-brand-500/30';
          if (node.type === 'cost') badgeColor = 'bg-rose-500/20 text-rose-400 border border-rose-500/30';

          const connectedEdges = graphData.edges.filter(e => e.source === node.id || e.target === node.id);

          return (
            <div key={node.id} className="p-4 bg-slate-950/70 rounded-xl border border-slate-800 hover:border-slate-700 transition">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase text-white font-mono">{node.id}</span>
                <span className={`px-2 py-0.5 text-[10px] font-semibold rounded uppercase ${badgeColor}`}>
                  {node.type}
                </span>
              </div>
              <div className="text-sm font-semibold text-slate-200 mt-1">{node.data?.label}</div>
              <div className="text-[11px] text-slate-500 mt-3 pt-2 border-t border-slate-800/80">
                Connected to {connectedEdges.length} dependent nodes
              </div>
            </div>
          );
        })}
      </div>

      <div className="p-4 bg-slate-950/40 rounded-xl border border-slate-800 text-xs text-slate-400">
        <span className="font-semibold text-white">Graph Dependencies:</span>{' '}
        {graphData.edges.map(e => `${e.source} → ${e.target}`).join('  |  ')}
      </div>
    </div>
  );
};

