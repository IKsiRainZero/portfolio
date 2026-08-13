import { useState, useEffect, useCallback } from 'react';
import type { Project, WorkspaceSummary } from './types';
import { api } from './api/client';
import { Header, SplitPane } from './components/Layout';
import { ProjectGroup, WorkspaceSummary as WSS, ProjectDetail } from './components/Dashboard';
import { ChatPanel } from './components/ChatPanel';
import { TraceTimeline } from './components/Observability';
import { useChat } from './hooks/useChat';
import styles from './App.module.css';

export default function App() {
  const [summary, setSummary] = useState<WorkspaceSummary | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [showTraces, setShowTraces] = useState(false);
  const { messages, sending, sseDisconnected, send } = useChat();

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, p] = await Promise.all([api.getWorkspaceSummary(), api.getProjects()]);
      setSummary(s);
      setProjects(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleSend = (text: string) => {
    send(text, { current_view: selectedProject ? 'project_detail' : 'dashboard', active_project: selectedProject || '' });
  };

  const activeProjects = projects.filter(p => p.status === 'active');
  const dormantProjects = projects.filter(p => p.status === 'dormant');
  const otherProjects = projects.filter(p => !['active', 'dormant'].includes(p.status));

  const detailPanel = selectedProject && projects.find(p => p.name === selectedProject);

  const dashboard = (
    <div className={styles.dashboard}>
      {error && <div className={styles.error}>{error} <button onClick={refresh}>Retry</button></div>}
      {loading && <div className={styles.skeleton}>Loading...</div>}
      {!loading && !error && (
        <>
          {summary && <WSS summary={summary} />}
          <button className={styles.newBtn} onClick={() => handleSend('Initialize a new project: ')}>+ New Project</button>
          <button className={styles.traceBtn} onClick={() => setShowTraces(!showTraces)}>
            {showTraces ? 'Hide Traces' : 'Observability'}
          </button>
          {showTraces && <TraceTimeline project={selectedProject || undefined} />}
          <ProjectGroup title="Active" projects={activeProjects} onSelect={setSelectedProject} />
          <ProjectGroup title="Dormant" projects={dormantProjects} onSelect={setSelectedProject} />
          {otherProjects.length > 0 && <ProjectGroup title="Other" projects={otherProjects} onSelect={setSelectedProject} />}
        </>
      )}
    </div>
  );

  return (
    <div className={styles.app}>
      <Header onRefresh={refresh} loading={loading} />
      <SplitPane
        left={detailPanel
          ? <ProjectDetail project={detailPanel} onClose={() => setSelectedProject(null)} />
          : dashboard
        }
        right={<ChatPanel messages={messages} onSend={handleSend} sending={sending} sseDisconnected={sseDisconnected} onReconnect={() => {}} />}
      />
    </div>
  );
}
