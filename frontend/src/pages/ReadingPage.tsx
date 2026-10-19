import { useEffect, useRef, useState } from 'react';
import { jsonPost, request, RequestError } from '../api/client';
import type { Collection, Health, Job, Report } from '../api/types';
import { MaterialList } from '../components/MaterialList';
import { ReportView } from '../components/ReportView';
import { LanguageControls, useUi, errorMessage } from '../i18n';

export function ReadingPage({ onHome }: { onHome?: () => void }) {
  const { settings, update, t } = useUi();
  const [health, setHealth] = useState<Health | null>(null);
  const [collection, setCollection] = useState<Collection | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const upload = useRef<HTMLInputElement>(null);
  const generation = useRef(0);
  const alive = useRef(true);
  const polling = job?.status === 'queued' || job?.status === 'running';
  const busy = saving || polling;
  const materials = collection?.materials ?? [];
  const budgetLow = health?.provider === 'qwen' && health.validation_budget_remaining_cny != null && health.validation_budget_remaining_cny < 1;
  const ready = (collection?.can_generate ?? false) && !budgetLow;

  async function initialize() {
    setError('');
    try {
      const state = await request<Health>('/health');
      if (!alive.current) return;
      setHealth(state);
      const linked = new URLSearchParams(location.search).get('collection');
      const saved = linked && /^[a-f0-9]{32}$/.test(linked) ? linked : sessionStorage.getItem('ai-radar-collection');
      let next: Collection | null = null;
      if (saved) { try { next = await request<Collection>(`/collections/${saved}`); } catch (err) { if (!(err instanceof RequestError) || err.detail.code !== 'NOT_FOUND') throw err; } }
      next ??= await jsonPost<Collection>('/collections', {});
      if (!alive.current) return;
      sessionStorage.setItem('ai-radar-collection', next.collection_id);
      setCollection(next);
      if (next.last_job_id) {
        const restored = await request<Job>(`/jobs/${next.last_job_id}`);
        if (!alive.current || restored.status === 'cancelled') return;
        if (['succeeded', 'failed'].includes(restored.status) && restored.report_id) {
          const output = await request<Report>(`/reports/${restored.report_id}`);
          if (!alive.current) return;
          setReport(output);
        }
        setJob(restored);
      }
    } catch (err) { if (alive.current) setError(errorMessage(err, settings?.ui_language)); }
  }

  useEffect(() => { alive.current = true; void initialize(); return () => { alive.current = false; generation.current += 1; }; }, []);
  useEffect(() => {
    if (!polling || !job) return;
    const expected = generation.current;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await request<Job>(`/jobs/${job!.job_id}`);
        if (stopped || expected !== generation.current) return;
        if (['succeeded', 'failed'].includes(next.status) && next.report_id) {
          const output = await request<Report>(`/reports/${next.report_id}`);
          if (stopped || expected !== generation.current) return;
          setReport(output);
        }
        setJob(next); setError('');
        if (next.status === 'queued' || next.status === 'running') timer = setTimeout(poll, 2000);
      } catch (err) { if (!stopped && expected === generation.current) { setError(errorMessage(err, settings?.ui_language)); timer = setTimeout(poll, 2000); } }
    }
    timer = setTimeout(poll, 800);
    return () => { stopped = true; clearTimeout(timer); };
  }, [job?.job_id, polling]);

  async function mutate(action: () => Promise<Collection>) {
    setSaving(true); setError('');
    try { const next = await action(); generation.current += 1; setJob(null); setReport(null); setCollection(next); }
    catch (err) { setError(errorMessage(err, settings?.ui_language)); }
    finally { setSaving(false); }
  }

  async function add(files: File[]) {
    if (!collection) return;
    const form = new FormData(); files.forEach(file => form.append('files', file)); form.append('expected_revision', String(collection.revision));
    await mutate(() => request<Collection>(`/collections/${collection.collection_id}/uploads`, { method: 'POST', body: form }));
  }
  async function replace(id: string, file: File) {
    if (!collection) return;
    const form = new FormData(); form.append('file', file); form.append('expected_revision', String(collection.revision));
    await mutate(() => request<Collection>(`/collections/${collection.collection_id}/materials/${id}/file`, { method: 'PUT', body: form }));
  }
  async function remove(id: string) {
    if (!collection) return;
    await mutate(() => request<Collection>(`/collections/${collection.collection_id}/materials/${id}?expected_revision=${collection.revision}`, { method: 'DELETE' }));
  }
  async function generate(retry = false) {
    if (!collection) return;
    setSaving(true); setError(''); if (!(retry && job?.report_id && job.language !== 'zh') && job?.kind !== 'language') setReport(null); generation.current += 1;
    try {
      setHealth(await request<Health>('/health'));
      const next = retry && job?.report_id && job.language !== 'zh'
        ? await jsonPost<Job>(`/reports/${job.report_id}/language-jobs`, { report_language: job.language }, crypto.randomUUID())
        : retry && job ? await jsonPost<Job>(`/jobs/${job.job_id}/retry`, {}, crypto.randomUUID())
        : await jsonPost<Job>('/reading-jobs', { collection_id: collection.collection_id, expected_revision: collection.revision, report_language: settings?.report_language ?? 'zh' }, crypto.randomUUID());
      setJob(next);
    } catch (err) { setError(errorMessage(err, settings?.ui_language)); }
    finally { setSaving(false); }
  }
  async function exit() {
    if (!job) return;
    setSaving(true); setError(''); generation.current += 1;
    try { await jsonPost<Job>(`/jobs/${job.job_id}/cancel`, {}); setJob(null);
      if (job.kind === 'language' && report) await update({ report_language: report.language });
      else setReport(null); }
    catch (err) { setError(errorMessage(err, settings?.ui_language)); }
    finally { setSaving(false); }
  }

  useEffect(() => {
    if (!report || !settings || report.language === settings.report_language || (job?.kind === 'language' && job.language === settings.report_language)
        || (job?.status === 'failed' && job.language === settings.report_language)) return;
    let stopped = false;
    void (async () => {
      if (job?.kind === 'language' && ['queued', 'running'].includes(job.status) && job.language !== settings.report_language)
        await jsonPost<Job>(`/jobs/${job.job_id}/cancel`, {});
      return jsonPost<Job>(`/reports/${report.report_id}/language-jobs`, { report_language: settings.report_language }, crypto.randomUUID());
    })().then(next => { if (!stopped) { generation.current += 1; setJob(next); } })
      .catch(err => { if (!stopped) setError(errorMessage(err, settings?.ui_language)); });
    return () => { stopped = true; };
  }, [report?.report_id, settings?.report_language, job?.job_id]);

  return <>
    <header className="topbar"><a href="#home" onClick={onHome} className="brand" aria-label="AI Radar home"><span className="brand-mark" aria-hidden="true">◎</span><span>AI <b>Radar</b></span></a><div className="topbar-right"><a href="#home" onClick={onHome}>{t('发现论文', 'Discover papers')}</a><LanguageControls /></div></header>
    <main className="workspace"><div className="page-heading"><div><p className="eyebrow">FROM PAPER TO UNDERSTANDING</p><h1>{t('把论文读明白。', 'Make sense of the paper.')}</h1><p className="subtitle">{t('从速览选择论文，也可上传 PDF；一篇单读，多篇联合对照。', 'Select papers from an overview or upload PDFs. Read one paper or compare several together.')}</p></div><span className="mode-pill">{collection?.derived_mode === 'joint' ? t('联合精读', 'Joint reading') : collection?.derived_mode === 'single' ? t('单篇精读', 'Single-paper reading') : t('待添加', 'No papers yet')}</span></div>
      <div className="workspace-grid"><aside className="paper-panel panel"><div className="panel-title"><h2>{t('精读材料', 'Reading materials')}</h2><span className="count">{materials.length} / 10</span></div><p className="muted small">{t('从速览带入或批量上传正文；全部就绪后主动生成。', 'Bring papers from an overview or upload PDFs. Generate when all sources are ready.')}</p>
        <input ref={upload} className="visually-hidden" type="file" multiple accept="application/pdf,.pdf" aria-label={t('上传论文 PDF', 'Upload paper PDFs')} onChange={event => { const files = Array.from(event.target.files ?? []); if (files.length) void add(files); event.target.value = ''; }} />
        <button className="upload-area" disabled={busy || !collection || materials.length >= 10} onClick={() => upload.current?.click()}><span className="upload-symbol" aria-hidden="true">↑</span><strong>{saving ? t('正在检查正文…', 'Checking the PDF…') : materials.length ? t('继续添加 PDF', 'Add more PDFs') : t('选择论文 PDF', 'Choose paper PDFs')}</strong><span>{t('最多 10 篇 · 每篇最大 50 MiB / 150 页', 'Up to 10 papers · 50 MiB / 150 pages per PDF')}</span><span className="upload-note">{t('扫描件暂不支持，文件留在当前本机服务会话', 'Scanned PDFs are not supported; files stay in this local session')}</span></button>
        <MaterialList materials={materials} busy={busy} onReplace={(id, file) => void replace(id, file)} onRemove={id => void remove(id)} />
        {collection?.blocking_reasons.map((reason, index) => <p className="error-text" key={index}>{settings?.ui_language === 'en' ? (materials.length ? 'A paper needs a valid full-text PDF. Replace or remove failed materials.' : 'Upload a paper PDF first.') : reason}</p>)}
        {budgetLow && <p className="error-text">{t('开发验证预算仅余约', 'The development validation budget has only')} ¥{health?.validation_budget_remaining_cny?.toFixed(4)} {t('，已暂停新的模型任务；现有材料仍可编辑。', 'remaining; new model tasks are paused. You can still edit materials.')}</p>}
        <div className="generation-controls"><label>{t('报告语言', 'Report language')} <strong>{settings?.report_language === 'en' ? 'English' : settings?.report_language === 'bilingual' ? '中文 + English' : '中文'}</strong></label><button className="primary" disabled={!ready || busy} onClick={() => void generate()}>{saving ? t('处理中…', 'Processing…') : polling ? t('正在生成…', 'Generating…') : report ? t('重新生成报告', 'Regenerate report') : t('生成报告', 'Generate report')}<span aria-hidden="true">↗</span></button><p className="small muted">{t('点击后调用模型 API。任何失败材料都会阻止启动；报告完成前不自动重复请求。', 'This calls the model API. Failed materials block generation; requests are not repeated automatically.')} {health?.provider === 'qwen' ? 'Qwen' : 'Claude'}</p></div>
        {health && !health.model_configured && <div className="config-note"><strong>{t('还需配置本机 API Key', 'Configure a local API key')}</strong><p>{t('在项目根目录 .env 填写', 'Set')} {health?.provider === 'qwen' ? 'QWEN_API_KEY' : 'ANTHROPIC_API_KEY'} {t('再点击生成。密钥无需发到聊天中。', 'in the project .env, then generate. Keep the key private.')}</p></div>}
        <div className="service-status"><span className={health ? 'dot ready' : 'dot'} />{health ? t('本机处理服务已连接', 'Local service connected') : t('等待处理服务', 'Waiting for local service')}</div>
      </aside>
      <div className="reading-content" aria-live="polite">
        {job?.usage.budget_limit_cny != null && <aside className="config-note"><strong>验证预算：¥{job.usage.budget_accounted_cny?.toFixed(4) ?? '0'} / ¥{job.usage.budget_limit_cny}</strong><p>已返回用量的请求估计 ¥{job.usage.estimated_cost_cny?.toFixed(4) ?? '0'}（含 PDF 解析费）。{job.usage.unknown_usage_calls > 0 && `${job.usage.unknown_usage_calls} 次请求用量未知，已保守计入预算。`}金额以平台账单为准。</p></aside>}
        {error && <div className="error-banner" role="alert"><strong>{t('操作未完成', 'Action not completed')}</strong><p>{error}</p>{!collection && <button className="text-button" onClick={() => void initialize()}>{t('重新连接', 'Reconnect')}</button>}</div>}
        {job?.status === 'failed' && <div className="error-banner" role="alert"><strong>{job.kind === 'language' ? t('语言转换失败', 'Language conversion failed') : t('报告生成失败', 'Report generation failed')}</strong><p>{job.error ? errorMessage(job.error, settings?.ui_language) : t('未获得完整报告。', 'No complete report was returned.')}</p><div className="inline-actions"><button className="primary compact" disabled={busy} onClick={() => void generate(true)}>{t('重新生成', 'Regenerate')}</button><button className="secondary" disabled={busy} onClick={() => void exit()}>{t('退出', 'Exit')}</button></div></div>}
        {polling && <section className="progress-card panel"><span className="spinner" aria-hidden="true"/><h2>{t(job.phase, job.kind === 'language' ? 'Converting report language…' : 'Processing paper and reviewing report…')}</h2><p>{t('全文读取后，分阶段讲解并独立审校。', 'Reading full text, explaining in stages, then reviewing independently.')}</p><p className="muted small">{t('已处理', 'Processed')} {job.completed_pages} / {job.total_pages} {t('个物理页', 'PDF pages')}</p><button className="secondary" disabled={saving} onClick={() => void exit()}>{t('退出生成，保留材料', 'Exit generation and keep materials')}</button><p className="small muted">{t('退出会停止后续请求；已发送的请求可能产生费用。', 'Exiting stops future requests; requests already sent may incur charges.')}</p></section>}
        {report && <ReportView report={report} job={job} />}
        {!report && !polling && <section className="empty-report panel"><div className="layered-icon" aria-hidden="true"><span/><span/><span>✦</span></div><p className="eyebrow">A CLEARER VIEW</p><h2>{t('从“看过”，到“看懂”。', 'From reading to understanding.')}</h2><p className="muted">{t('材料就绪后，点击生成报告。', 'When materials are ready, generate the report.')}<br/>{t('把研究放回它的坐标，沿着方法与证据读下去。', 'Place the work in context, then follow its methods and evidence.')}</p><div className="template-preview">{(collection?.derived_mode === 'joint' ? (settings?.ui_language === 'en' ? ['Shared research scope', 'Shared knowledge and concepts', 'Research routes', 'Evidence and results', 'Connections and limits', 'Joint takeaways'] : ['共同研究范围', '共同知识与概念差异', '研究路线对照', '证据与结果对照', '互补、分歧与边界', '联合知识收获']) : (settings?.ui_language === 'en' ? ['30-second card', 'Research position', 'What to know first', 'Core idea', 'Method', 'Equations', 'Experiments', 'Value', 'Check yourself', 'Read next'] : ['30 秒速读卡', '研究定位与具体贡献', '读之前先备好', '核心思想', '方法拆解', '公式精讲', '实验怎么读', '有什么用', '检验一下', '接下来读什么'])).map((title, index) => <div key={title}><span>{String(index + 1).padStart(2, '0')}</span>{title}</div>)}</div><p className="small muted empty-note">{t('报告将使用真实论文与模型输出；这里仅展示固定栏目。', 'The report uses real papers and model output; these are the fixed sections.')}</p></section>}
      </div></div>
    </main><footer className="footer">AI Radar · {t('学习，从发现开始。', 'Learning starts with discovery.')}<span>{t('当前会话的论文会在处理服务重启后清除', 'Session papers are cleared when the local service restarts')}</span></footer>
  </>;
}
