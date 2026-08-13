import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import CardEditor from '../src/components/Canvas/CardEditor';

const entry = () => ({
  id: '1', title: 'T', content: 'C', entry_type: 'known', layer_id: null,
  dimension_id: 'd1', source_type: 'manual', source_link: '', status: 'confirmed',
  tags: [], tag_ids: [], confidence: 100, x: 0, y: 0, width: 200, height: 120, z_depth: 0,
  created_at: '', updated_at: '',
} as any);
const layers = [{ id: 'l1', dimension_id: 'd1', name: '细胞', level: 0, description: '', entry_count: 0 }];

describe('CardEditor', () => {
  it('saves edited title', () => {
    const onSave = vi.fn();
    render(<CardEditor entry={entry()} layers={layers} onSave={onSave} onDelete={() => {}} onClose={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText('标题'), { target: { value: '新标题' } });
    fireEvent.click(screen.getByText('保存'));
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ title: '新标题' }));
  });

  it('toggles a layer tag', () => {
    const onSave = vi.fn();
    render(<CardEditor entry={entry()} layers={layers} onSave={onSave} onDelete={() => {}} onClose={() => {}} />);
    fireEvent.click(screen.getByText('细胞'));
    fireEvent.click(screen.getByText('保存'));
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ tag_ids: ['l1'] }));
  });

  it('calls onDelete', () => {
    const onDelete = vi.fn();
    render(<CardEditor entry={entry()} layers={layers} onSave={() => {}} onDelete={onDelete} onClose={() => {}} />);
    fireEvent.click(screen.getByText('删除'));
    expect(onDelete).toHaveBeenCalledWith('1');
  });
});
