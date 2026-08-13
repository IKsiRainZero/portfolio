export interface ProjectRisk {
  level: 'warning' | 'error' | 'info';
  text: string;
  source: string;
}

export interface TestStatus {
  total: number;
  passed: number;
  failed: number;
  last_run: string;
}

export interface ActivityItem {
  type: 'git.commit' | 'session.record' | 'trace.operation';
  time: string;
  summary: string;
  hash?: string;
}

export interface Project {
  name: string;
  status: 'active' | 'dormant' | 'ready' | 'archived' | 'unknown';
  phase: string;
  description: string;
  tests: TestStatus;
  activity: ActivityItem[];
  risks: ProjectRisk[];
  constitution_files: string[];
  git_status: { uncommitted: number; branch: string; last_commit: string } | null;
}

export interface WorkspaceSummary {
  total_projects: number;
  active: number;
  dormant: number;
  total_risks: number;
}

export interface TraceRecord {
  id: string;
  timestamp: string;
  source: string;
  operation: string;
  target: string;
  input_summary: string;
  output_summary: string;
  duration_ms: number;
  status: 'ok' | 'warning' | 'error';
  parent_trace_id: string | null;
}

export interface ClaudeSession {
  session_id: string;
  project_dir: string;
  project_label: string;
  project_path: string;
  title: string;
  time: string;
  size_bytes: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
  toolCall?: { name: string; traceId: string; status: 'running' | 'done' | 'error'; result?: unknown };
}

export type SSEEventType =
  | 'context' | 'message_start' | 'message_delta' | 'message_end'
  | 'tool_start' | 'tool_progress' | 'tool_end'
  | 'confirm_required' | 'error';
