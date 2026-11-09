export interface CompanySnapshot {
  company_name: string;
  stage: string;
  currency: string;
  synthetic_data_badge: boolean;
  mrr: number;
  arr: number;
  cash_balance: number;
  runway_months: number;
  monthly_burn_net: number;
  gross_margin: number;
  paying_customers: number;
  monthly_churn_rate: number;
  cac: number;
  ltv: number;
  monthly_visitors: number;
  trial_to_paid_conversion: number;
  infra_cost_monthly: number;
  support_headcount: number;
  support_cost_monthly: number;
}

export interface TaskItem {
  id: string;
  owner_agent: string;
  depends_on: string[];
  status: 'pending' | 'running' | 'done' | 'failed' | 'retrying' | 'blocked';
  attempts: number;
  error?: string;
}

export interface FindingItem {
  agent: string;
  task_id: string;
  claim: string;
  recommendation: string;
  assumptions: any[];
  evidence: any[];
  confidence: number;
  limitations: string[];
}

export interface EventItem {
  ts: string;
  type: string;
  agent: string;
  payload: any;
}

export const API_BASE = '/api';

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Failed to fetch health');
  return res.json();
}

export async function fetchCompany(): Promise<CompanySnapshot> {
  const res = await fetch(`${API_BASE}/company`);
  if (!res.ok) throw new Error('Failed to fetch company snapshot');
  return res.json();
}

export async function submitDecision(query: string, constraints?: Record<string, any>) {
  const res = await fetch(`${API_BASE}/decisions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, constraints })
  });
  if (!res.ok) throw new Error('Failed to submit decision');
  return res.json();
}

export async function fetchDecisionStatus(decisionId: string) {
  const res = await fetch(`${API_BASE}/decisions/${decisionId}`);
  if (!res.ok) throw new Error('Failed to fetch status');
  return res.json();
}

export async function fetchDecisionReport(decisionId: string) {
  const res = await fetch(`${API_BASE}/decisions/${decisionId}/report`);
  if (!res.ok) throw new Error('Failed to fetch report');
  return res.json();
}

export async function injectFailure(
  decisionId: string,
  agent: string,
  mode: string,
  persist: boolean = false,
  failAttempts: number = 1
) {
  const res = await fetch(`${API_BASE}/decisions/${decisionId}/inject-failure`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ agent, mode, persist, fail_attempts: failAttempts })
  });
  if (!res.ok) throw new Error('Failed to inject failure');
  return res.json();
}

export async function approveDecision(decisionId: string, action: string, notes?: string) {
  const res = await fetch(`${API_BASE}/decisions/${decisionId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, notes })
  });
  if (!res.ok) throw new Error('Failed to record approval');
  return res.json();
}

export async function fetchHistory() {
  const res = await fetch(`${API_BASE}/history`);
  if (!res.ok) throw new Error('Failed to fetch history');
  return res.json();
}

export async function fetchCompanyGraph() {
  const res = await fetch(`${API_BASE}/graph`);
  if (!res.ok) throw new Error('Failed to fetch graph');
  return res.json();
}

