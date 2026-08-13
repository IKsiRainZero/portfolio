import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import TagPool from '../src/components/Canvas/TagPool';

const layers = [
  { id: 'l1', dimension_id: 'd1', name: '细胞', level: 0, description: '', entry_count: 0 },
  { id: 'l2', dimension_id: 'd1', name: '社会', level: 5, description: '', entry_count: 0 },
];
const entries = [{ id: 'e1', tag_ids: ['l1'] }] as any;

describe('TagPool', () => {
  it('shows count per layer tag', () => {
    render(<TagPool layers={layers} entries={entries} />);
    expect(screen.getByText('细胞')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('marks empty layers as blind spots', () => {
    const { container } = render(<TagPool layers={layers} entries={entries} />);
    expect(container.querySelectorAll('[data-empty="true"]').length).toBe(1);
  });
});
