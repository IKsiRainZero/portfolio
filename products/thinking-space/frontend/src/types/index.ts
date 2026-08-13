export interface Layer {
  id: string;
  dimension_id: string;
  name: string;
  level: number;
  description: string;
  entry_count: number;
}

export interface Dimension {
  id: string;
  name: string;
  description: string;
  sort_order: number;
  layers: Layer[];
}

export interface Entry {
  id: string;
  title: string;
  content: string;
  entry_type: 'known' | 'unknown' | 'question';
  layer_id: string | null;
  dimension_id: string;
  source_type: 'manual' | 'portfolio_index' | 'conversation';
  source_link: string;
  status: 'pending' | 'confirmed' | 'ignored';
  tags: string[];
  tag_ids: string[];
  confidence: number;
  x: number;
  y: number;
  width: number;
  height: number;
  z_depth: number;
  created_at: string;
  updated_at: string;
}

export interface LayerDiagnosis {
  level: number;
  name: string;
  relation: string;
  gaps: string[];
  suggestions: string[];
  new_questions: string[];
  existing_entries_highlighted: string[];
  new_suggested_entries: { title: string; entry_type: string; content: string }[];
}

export interface LayerLink {
  id: string;
  source_layer_id: string;
  target_layer_id: string;
  relation_type: string;
  note: string;
}

export type DiagnosisEvent =
  | { event: 'layer_start'; data: { level: number; name: string } }
  | { event: 'layer_complete'; data: LayerDiagnosis }
  | { event: 'diagnose_end'; data: { question: string; dimension: string; layers: LayerDiagnosis[]; gap_summary: string } }
  | { event: 'error'; data: { level?: number; message: string } };
