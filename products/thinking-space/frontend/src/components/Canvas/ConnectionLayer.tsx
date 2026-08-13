import type { Entry } from '../../types';

interface LinkShape { id: string; source_entry_id: string; target_entry_id: string; }
interface Props {
  entries: Entry[];
  links: LinkShape[];
  onDeleteLink: (id: string) => void;
}

function bezier(sx: number, sy: number, tx: number, ty: number): string {
  const dx = Math.max(40, Math.abs(tx - sx) * 0.5);
  return `M ${sx} ${sy} C ${sx + dx} ${sy}, ${tx - dx} ${ty}, ${tx} ${ty}`;
}

export default function ConnectionLayer({ entries, links, onDeleteLink }: Props) {
  const byId = new Map(entries.map((e) => [e.id, e]));
  return (
    <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', overflow: 'visible', pointerEvents: 'none' }}>
      {links.map((link) => {
        const s = byId.get(link.source_entry_id);
        const t = byId.get(link.target_entry_id);
        if (!s || !t) return null;
        const sx = s.x + s.width, sy = s.y + s.height / 2;
        const tx = t.x, ty = t.y + t.height / 2;
        return (
          <path key={link.id} d={bezier(sx, sy, tx, ty)} fill="none" stroke="#8e8e93" strokeWidth={2}
                style={{ pointerEvents: 'stroke', cursor: 'pointer' }}
                onClick={() => onDeleteLink(link.id)} />
        );
      })}
    </svg>
  );
}
