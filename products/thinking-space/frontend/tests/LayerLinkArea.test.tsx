import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import LayerLinkArea from '../src/components/ChainEditor/LayerLinkArea';

const layers = [
  { id: 'l1', dimension_id: 'd1', name: '细胞', level: 0, description: '', entry_count: 0 },
  { id: 'l2', dimension_id: 'd1', name: '组织', level: 1, description: '', entry_count: 0 },
];
const links = [{ id: 'k1', source_layer_id: 'l1', target_layer_id: 'l2', relation_type: 'leads_to', note: '' }];

describe('LayerLinkArea', () => {
  const base = { layers, links, onCreateLink: vi.fn(), onDeleteLink: vi.fn() };

  it('renders layer nodes', () => {
    render(<LayerLinkArea {...base} />);
    expect(screen.getByText('细胞')).toBeInTheDocument();
    expect(screen.getByText('组织')).toBeInTheDocument();
  });

  it('renders a bezier path per link', () => {
    const { container } = render(<LayerLinkArea {...base} />);
    const path = container.querySelector('path');
    expect(path).toBeTruthy();
    expect(path!.getAttribute('d')).toMatch(/C/);
  });

  it('creates link by clicking two nodes', () => {
    const onCreateLink = vi.fn();
    render(<LayerLinkArea {...base} links={[]} onCreateLink={onCreateLink} />);
    fireEvent.click(screen.getByText('细胞'));
    fireEvent.click(screen.getByText('组织'));
    expect(onCreateLink).toHaveBeenCalledWith('l1', 'l2');
  });

  it('renders no path when link references a layer not in the list', () => {
    const badLinks = [
      { id: 'k_bad', source_layer_id: 'l1', target_layer_id: 'nonexistent', relation_type: 'leads_to', note: '' },
    ];
    const { container } = render(<LayerLinkArea {...base} links={badLinks} />);
    expect(container.querySelectorAll('path').length).toBe(0);
  });
});
