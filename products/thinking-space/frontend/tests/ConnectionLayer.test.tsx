import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ConnectionLayer from '../src/components/Canvas/ConnectionLayer';

const entries = [
  { id: 'a', x: 0, y: 0, width: 100, height: 60 },
  { id: 'b', x: 300, y: 200, width: 100, height: 60 },
] as any;

describe('ConnectionLayer', () => {
  it('renders a cubic bezier path per link', () => {
    const { container } = render(
      <ConnectionLayer entries={entries} links={[{ id: 'L', source_entry_id: 'a', target_entry_id: 'b' }]} onDeleteLink={() => {}} />
    );
    const path = container.querySelector('path');
    expect(path).toBeTruthy();
    expect(path!.getAttribute('d')).toMatch(/^M.*C/); // cubic bezier command present
  });

  it('deletes link on path click', () => {
    const onDelete = vi.fn();
    const { container } = render(
      <ConnectionLayer entries={entries} links={[{ id: 'L', source_entry_id: 'a', target_entry_id: 'b' }]} onDeleteLink={onDelete} />
    );
    const path = container.querySelector('path')!;
    path.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(onDelete).toHaveBeenCalledWith('L');
  });

  it('skips links with missing endpoints', () => {
    const { container } = render(
      <ConnectionLayer entries={entries} links={[{ id: 'X', source_entry_id: 'a', target_entry_id: 'ghost' }]} onDeleteLink={() => {}} />
    );
    expect(container.querySelector('path')).toBeNull();
  });
});
