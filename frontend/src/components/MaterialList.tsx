import { useRef } from 'react';
import type { Material } from '../api/types';
import { useUi, errorMessage } from '../i18n';

export function MaterialList({ materials, busy, onReplace, onRemove }: { materials: Material[]; busy: boolean; onReplace: (id: string, file: File) => void; onRemove: (id: string) => void }) {
  const { t, settings } = useUi();
  const replace = useRef<HTMLInputElement>(null);
  const selected = useRef('');
  return <div className="material-list">
    <input ref={replace} className="visually-hidden" type="file" accept="application/pdf,.pdf" aria-label={t('重新上传论文', 'Replace paper PDF')} onChange={event => { const file = event.target.files?.[0]; if (file) onReplace(selected.current, file); event.target.value = ''; }} />
    {materials.map(material => <article className={`material ${material.status}`} key={material.material_id}>
      <div className="file-icon" aria-hidden="true">PDF</div>
      <div className="material-detail"><div className="filename">{material.origin === 'arxiv' ? material.original_filename : material.filename}</div><div className="muted small">{material.content_source === 'arxiv' ? `arXiv:${material.paper_id}` : t('上传 PDF', 'Uploaded PDF')} · {t('版本', 'revision')} {material.revision} · {(material.byte_size / 1024 / 1024).toFixed(2)} MiB{material.status === 'ready' && ` · ${material.page_count} ${t('页', 'pages')}`}</div>
        {material.error && <p className="error-text">{errorMessage(material.error, settings?.ui_language)}</p>}
        {material.warnings.map((warning, index) => <p className="small muted" key={index}>{warning}</p>)}
        <div className="material-actions"><button className="text-button" disabled={busy} onClick={() => { selected.current = material.material_id; replace.current?.click(); }}>{t('重新上传', 'Replace PDF')}</button><button className="text-button danger" disabled={busy} onClick={() => onRemove(material.material_id)}>{t('移除', 'Remove')}</button></div>
      </div>
      <span className={`status ${material.status}`}>{material.status === 'ready' ? t('正文就绪', 'Ready') : t('需处理', 'Needs attention')}</span>
    </article>)}
  </div>;
}
