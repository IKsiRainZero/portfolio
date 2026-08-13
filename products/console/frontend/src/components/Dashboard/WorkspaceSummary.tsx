import type { WorkspaceSummary as WS } from '../../types';

export default function WorkspaceSummary({ summary }: { summary: WS }) {
  return (
    <div style={{ display: 'flex', gap: '24px', padding: '12px 0', fontSize: '13px', color: '#888' }}>
      <span><strong>{summary.active}</strong> active</span>
      <span><strong>{summary.dormant}</strong> dormant</span>
      <span><strong>{summary.total_risks}</strong> risks</span>
      <span><strong>{summary.total_projects}</strong> total</span>
    </div>
  );
}
