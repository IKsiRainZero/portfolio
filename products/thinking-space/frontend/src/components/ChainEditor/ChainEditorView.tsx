import type { Dimension, Layer, LayerLink } from '../../types';
import ChainList from './ChainList';
import LayerList from './LayerList';
import LayerLinkArea from './LayerLinkArea';
import styles from './ChainEditor.module.css';

interface Props {
  dimensions: Dimension[];
  activeId: string;
  layers: Layer[];
  layerLinks: LayerLink[];
  onSelectChain: (id: string) => void;
  onCreateChain: (name: string) => void;
  onRenameChain: (id: string, name: string) => void;
  onDeleteChain: (id: string) => void;
  onCreateLayer: (name: string) => void;
  onRenameLayer: (id: string, name: string) => void;
  onUpdateLayerDesc: (id: string, desc: string) => void;
  onDeleteLayer: (id: string) => void;
  onReorderLayers: (ids: string[]) => void;
  onCreateLayerLink: (s: string, t: string) => void;
  onDeleteLayerLink: (id: string) => void;
}

export default function ChainEditorView(p: Props) {
  return (
    <div className={styles.view}>
      <ChainList dimensions={p.dimensions} activeId={p.activeId} onSelect={p.onSelectChain}
        onCreate={p.onCreateChain} onRename={p.onRenameChain} onDelete={p.onDeleteChain} />
      <LayerList layers={p.layers} onCreate={p.onCreateLayer} onRename={p.onRenameLayer}
        onUpdateDesc={p.onUpdateLayerDesc} onDelete={p.onDeleteLayer} onReorder={p.onReorderLayers} />
      <LayerLinkArea layers={p.layers} links={p.layerLinks}
        onCreateLink={p.onCreateLayerLink} onDeleteLink={p.onDeleteLayerLink} />
    </div>
  );
}
