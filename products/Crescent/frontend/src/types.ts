export type PanelId = 'profile' | 'direction' | 'gap' | 'source' | 'path' | 'action';
export type PanelState = 'EMPTY' | 'READY_FOR_REVIEW' | 'CONFIRMED' | 'PARTIAL';

export interface WorkbenchEvent {
  event_type: string;
  panel_id: PanelId | '';
  payload: Record<string, unknown>;
  timestamp: string;
}

export const DEPENDENCIES: Record<PanelId, PanelId[]> = {
  profile: [],
  direction: ['profile'],
  gap: ['profile', 'direction'],
  source: ['direction'],
  path: ['direction', 'gap'],
  action: ['path'],
};

export const SEQUENCE: PanelId[] = ['profile', 'direction', 'gap', 'path', 'action'];

export const PANEL_LABELS: Record<PanelId, string> = {
  profile: '能力画像', direction: '匹配方向', gap: '差距分析',
  source: '数据来源', path: '学习路径', action: '下一步行动',
};
