import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ChainEditorView from '../src/components/ChainEditor/ChainEditorView';

const dims = [{ id: 'd1', name: '物质层次', description: '', sort_order: 0, layers: [] }] as any;
const layers = [{ id: 'l1', dimension_id: 'd1', name: '细胞', level: 0, description: '', entry_count: 0 }];

const noop = vi.fn();
const base = {
  dimensions: dims, activeId: 'd1', layers, layerLinks: [],
  onSelectChain: noop, onCreateChain: noop, onRenameChain: noop, onDeleteChain: noop,
  onCreateLayer: noop, onRenameLayer: noop, onUpdateLayerDesc: noop, onDeleteLayer: noop,
  onReorderLayers: noop, onCreateLayerLink: noop, onDeleteLayerLink: noop,
};

describe('ChainEditorView', () => {
  it('renders all three panels', () => {
    render(<ChainEditorView {...base} />);
    expect(screen.getByDisplayValue('物质层次')).toBeInTheDocument();
    expect(screen.getByText('层级（拖拽重排）')).toBeInTheDocument();
    expect(screen.getByText('层级逻辑链（点两个节点连线）')).toBeInTheDocument();
  });
});
