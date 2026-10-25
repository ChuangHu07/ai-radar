import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { jsonPost, request, RequestError } from '../api/client';
import type { Category, Collection, Job, OverviewJob, OverviewReport } from '../api/types';
import { researchWording } from '../components/researchWording';
import { revealEvidence } from '../components/evidenceNavigation';
import { LanguageControls, useUi, errorMessage } from '../i18n';

type Ranking = { status: string; auto_attempts: number; stopped: boolean; month: string | null; groups: { code: string; search_codes: string[]; count: number; official_name: string; zh_name: string }[]; error: string | null; source_url: string; source_state?: 'live' | 'bundled_verified' };

// Saved reports predate the illustrations. Keep their original JSON intact while displaying the verified scenes.
const currentScenes: Record<string, { theme: string; caption_zh: string; caption_en: string; kind: 'concept_illustration' }> = {
  '2610.13948': { theme: 'wiki-navigation-scene', caption_zh: '从起点文章沿可见链接前进，比较到达目标的路径。', caption_en: 'Follow visible links from a start article and compare routes to the target.', kind: 'concept_illustration' },
  '2610.13935': { theme: 'concept-mask-scene', caption_zh: '找出概念线索，隐藏一部分，再观察黑箱模型解释的变化。', caption_en: 'Find concept clues, hide some, and observe changes in a black-box explanation.', kind: 'concept_illustration' },
  '2610.13909': { theme: 'regression-table-scene', caption_zh: '在表格回归中比较训练目标，并检查统一早停的局限。', caption_en: 'Compare training objectives for tabular regression and inspect limits of global early stopping.', kind: 'concept_illustration' },
  '2610.13895': { theme: 'attention-role-scene', caption_zh: '同一模型组件遇到不同任务，观察它发挥的作用如何改变。', caption_en: 'See how one model component changes role across tasks.', kind: 'concept_illustration' },
  '2610.13889': { theme: 'tool-reliability-scene', caption_zh: '代理依据工具执行反馈，调整工具检索顺序。', caption_en: 'An agent uses tool execution feedback to adjust retrieval order.', kind: 'concept_illustration' },
};
const visualFor = (paper: OverviewReport['papers'][number]): NonNullable<OverviewReport['papers'][number]['visual']> => paper.visual ?? currentScenes[paper.paper_id];
const visualSrc = (paper: OverviewReport['papers'][number], language: 'zh' | 'en') => {
  const visual = visualFor(paper);
  const svg = language === 'en' ? visual.svg_en : visual.svg_zh;
  return svg ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}` : `/overview-visuals/${visual.theme}.svg`;
};

export function DiscoveryPage({ onReading }: { onReading: () => void }) {
  const [query, setQuery] = useState('');
  const [categories, setCategories] = useState<Category[]>([]);
  const [searching, setSearching] = useState(true);
  const [visible, setVisible] = useState(12);
  const { settings: settingsValue, update: updateSettings, t } = useUi();
  const [ranking, setRanking] = useState<Ranking | null>(null);
  const [rankingVisible, setRankingVisible] = useState(6);
  const [job, setJob] = useState<OverviewJob | null>(null);
  const [report, setReport] = useState<OverviewReport | null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [choices, setChoices] = useState<Record<string, 'use_abstract' | 'remove'>>({});
  const [selected, setSelected] = useState<string[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const generation = useRef(0);
  const languageSwitch = useRef('');
  const deepLinkStarted = useRef(false);
  const [languageJob, setLanguageJob] = useState<Job | null>(null);
  const [languageAttempt, setLanguageAttempt] = useState(0);
  const busy = saving || job?.status === 'running' || job?.status === 'queued' || job?.status === 'awaiting_decision';
  const waiting = job?.status === 'awaiting_decision';
  const failed = job?.papers.filter(p => p.acquisition_status === 'failed') ?? [];

  useEffect(() => {
    if (!pickerOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') setPickerOpen(false); };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [pickerOpen]);

  useEffect(() => {
    let active = true;
    const load = () => void request<Ranking>('/rankings').then(value => { if (active) setRanking(value); }).catch(() => {});
    load(); const timer = setInterval(load, 3000);
    return () => { active = false; clearInterval(timer); };
  }, []);

  async function toggleTag(code: string) {
    if (!settingsValue) return;
    const next = settingsValue.custom_categories.includes(code)
      ? settingsValue.custom_categories.filter(item => item !== code)
      : [...settingsValue.custom_categories, code];
    setSaving(true); setError('');
    try {
      await updateSettings({ custom_categories: next });
    } catch (err) {
      setError(errorMessage(err, settingsValue?.ui_language));
    } finally { setSaving(false); }
  }

  async function receive(next: OverviewJob, ticket: number) {
    if (ticket !== generation.current) return;
    if (['succeeded', 'failed'].includes(next.status) && next.report_id) {
      const output = await request<OverviewReport>(`/reports/${next.report_id}`);
      if (ticket !== generation.current) return;
      setReport(output);
    }
    setJob(next);
  }
  useEffect(() => {
    let stopped = false;
    setSearching(true);
    const timer = setTimeout(() => void request<Category[]>(`/categories?q=${encodeURIComponent(query)}`).then(rows => {
      if (!stopped) { setCategories(rows); setVisible(12); setSearching(false); }
    }).catch(err => { if (!stopped) { setError(errorMessage(err, settingsValue?.ui_language)); setSearching(false); } }), 180);
    return () => { stopped = true; clearTimeout(timer); };
  }, [query]);
  useEffect(() => {
    const ticket = generation.current;
    const saved = new URLSearchParams(location.search).get('overview_job') || sessionStorage.getItem('ai-radar-overview');
    if (saved) void request<OverviewJob>(`/jobs/${saved}`).then(next => receive(next, ticket)).catch(err => {
      if (ticket !== generation.current) return;
      if (err instanceof RequestError && err.detail.code === 'NOT_FOUND') sessionStorage.removeItem('ai-radar-overview');
      else setError(errorMessage(err, settingsValue?.ui_language));
    });
    return () => { generation.current += 1; };
  }, []);
  useEffect(() => {
    if (!job || !['queued', 'running'].includes(job.status)) return;
    const ticket = generation.current;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await request<OverviewJob>(`/jobs/${job.job_id}`);
        if (stopped || ticket !== generation.current) return;
        await receive(next, ticket);
        if (!stopped && ['queued', 'running'].includes(next.status)) timer = setTimeout(poll, 2000);
      } catch (err) { if (!stopped && ticket === generation.current) { setError(errorMessage(err, settingsValue?.ui_language)); timer = setTimeout(poll, 2000); } }
    };
    timer = setTimeout(poll, 800);
    return () => { stopped = true; clearTimeout(timer); };
  }, [job?.job_id, job?.status]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const paperIds = (params.get('read_papers')?.split(',') ?? [params.get('read_paper')]).filter((id): id is string => !!id);
    if (!paperIds.length || !job || !report || deepLinkStarted.current || job.status !== 'succeeded') return;
    if (paperIds.length > 10 || new Set(paperIds).size !== paperIds.length || paperIds.some(id => !report.papers.some(paper => paper.paper_id === id))) {
      setError(t('保存版指定的论文不在当前速览中。', 'The saved paper is not in this overview.'));
      return;
    }
    deepLinkStarted.current = true;
    setSaving(true);
    setError('');
    void jsonPost<Collection>('/collections', { from_overview_job_id: job.job_id, selected_paper_ids: paperIds })
      .then(collection => {
        sessionStorage.setItem('ai-radar-collection', collection.collection_id);
        const url = new URL(location.href);
        url.searchParams.delete('read_paper');
        url.searchParams.delete('read_papers');
        history.replaceState(null, '', url);
        onReading();
      })
      .catch(err => { setError(errorMessage(err, settingsValue?.ui_language)); deepLinkStarted.current = false; })
      .finally(() => setSaving(false));
  }, [job?.job_id, job?.status, report?.report_id]);

  useEffect(() => {
    if (!report || !settingsValue || report.language === settingsValue.report_language || (job?.status === 'failed' && job.language === settingsValue.report_language && languageAttempt === 0)) return;
    const key = `${report.report_id}:${settingsValue.report_language}:${languageAttempt}`;
    if (languageSwitch.current === key) return;
    languageSwitch.current = key;
    let stopped = false;
    void (async () => {
      try {
        if (languageJob && ['queued', 'running'].includes(languageJob.status) && languageJob.language !== settingsValue.report_language)
          await jsonPost<Job>(`/jobs/${languageJob.job_id}/cancel`, {});
        let next = await jsonPost<Job>(`/reports/${report.report_id}/language-jobs`, { report_language: settingsValue.report_language }, crypto.randomUUID());
        while (!stopped && ['queued', 'running'].includes(next.status)) {
          setLanguageJob(next);
          await new Promise(resolve => setTimeout(resolve, 1500));
          next = await request<Job>(`/jobs/${next.job_id}`);
        }
        if (stopped) return;
        setLanguageJob(next.status === 'failed' ? next : null);
        if (next.status === 'succeeded' && next.report_id) setReport(await request<OverviewReport>(`/reports/${next.report_id}`));
        else if (next.status === 'failed') setError(next.error ? errorMessage(next.error, settingsValue?.ui_language) : t('语言转换失败。', 'Language conversion failed.'));
      } catch (err) { if (!stopped) { setLanguageJob(null); setError(errorMessage(err, settingsValue?.ui_language)); } }
    })();
    return () => { stopped = true; };
  }, [report?.report_id, settingsValue?.report_language, languageAttempt]);

  async function start(category: Category | Ranking['groups'][number], retry = false) {
    if (retry && job?.report_id && job.language !== 'zh') { setError(''); setLanguageAttempt(value => value + 1); return; }
    setSaving(true); setError(''); setReport(null); setSelected([]); setChoices({});
    const ticket = ++generation.current;
    try {
      const next = retry && job ? await jsonPost<OverviewJob>(`/jobs/${job.job_id}/retry`, {}, crypto.randomUUID())
        : await jsonPost<OverviewJob>('/overview-jobs', { category_codes: 'search_codes' in category ? category.search_codes : [category.code], report_language: settingsValue?.report_language ?? 'zh' }, crypto.randomUUID());
      sessionStorage.setItem('ai-radar-overview', next.job_id);
      const url = new URL(location.href);
      url.searchParams.set('overview_job', next.job_id);
      history.replaceState(null, '', url);
      await receive(next, ticket);
    } catch (err) { if (ticket === generation.current) setError(errorMessage(err, settingsValue?.ui_language)); }
    finally { setSaving(false); }
  }
  async function refreshRanking() {
    setSaving(true); setError('');
    try { setRanking(await jsonPost<Ranking>('/rankings/fetch', {})); }
    catch (err) { setError(errorMessage(err, settingsValue?.ui_language)); }
    finally { setSaving(false); }
  }
  async function exit() {
    if (!job) return;
    setSaving(true); generation.current += 1;
    try { if (languageJob && ['queued', 'running'].includes(languageJob.status)) await jsonPost(`/jobs/${languageJob.job_id}/cancel`, {});
      await jsonPost(`/jobs/${job.job_id}/cancel`, {}); setJob(null); setReport(null); setLanguageJob(null); setChoices({}); sessionStorage.removeItem('ai-radar-overview');
      const url = new URL(location.href); url.searchParams.delete('overview_job'); history.replaceState(null, '', url); }
    catch (err) { setError(errorMessage(err, settingsValue?.ui_language)); }
    finally { setSaving(false); }
  }
  async function confirm() {
    if (!job) return;
    setSaving(true); setError('');
    try { await receive(await jsonPost<OverviewJob>(`/jobs/${job.job_id}/decisions`, { decisions: failed.map(p => ({ paper_id: p.paper_id, action: choices[p.paper_id] })) }), generation.current); }
    catch (err) { setError(errorMessage(err, settingsValue?.ui_language)); }
    finally { setSaving(false); }
  }
  async function addToReading() {
    if (!job || !selected.length) return;
    setSaving(true); setError('');
    try {
      const collection = await jsonPost<Collection>('/collections', { from_overview_job_id: job.job_id, selected_paper_ids: selected });
      sessionStorage.setItem('ai-radar-collection', collection.collection_id); setPickerOpen(false); onReading();
    } catch (err) { setError(errorMessage(err, settingsValue?.ui_language)); }
    finally { setSaving(false); }
  }
  const markdown = (text: string, key = '', pid = '') => <ReactMarkdown skipHtml remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}
    components={{ a: ({ href, children }) => href?.startsWith('#overview-') ? <a href={href} onClick={revealEvidence}>{children}</a> : <span>{children}</span> }}>
      {researchWording(text, key).replace(/\[(E\d{4})\]/g, (_, id: string) => `[${id}](#overview-${pid}-${id})`)}
    </ReactMarkdown>;
  const rows = query.trim() ? categories : categories.filter(c => c.kind === 'archive');
  return <>
    <header className="topbar"><a href="#home" className="brand"><span className="brand-mark" aria-hidden="true">◎</span><span>AI <b>Radar</b></span></a><div className="topbar-right">{report ? <button className="reading-entry" onClick={() => setPickerOpen(true)}>{t('论文精读', 'Deep reading')} ↗</button> : <a className="reading-entry" href="#reading" onClick={onReading}>{t('论文精读', 'Deep reading')} ↗</a>}<LanguageControls /></div></header>
    {pickerOpen && report && <div className="reading-picker-backdrop" onClick={() => setPickerOpen(false)}><section className="reading-picker" role="dialog" aria-modal="true" aria-labelledby="reading-picker-title" onClick={event => event.stopPropagation()}>
      <div className="reading-picker-head"><div><p className="eyebrow">SELECT PAPERS</p><h2 id="reading-picker-title">{t('选择精读论文', 'Choose papers to read')}</h2></div><button className="reading-picker-close" aria-label={t('关闭', 'Close')} onClick={() => setPickerOpen(false)}>×</button></div>
      <p className="muted small">{t('选择一篇单独精读，或选择多篇联合精读。进入后仍可调整材料。', 'Select one paper for a close reading or several for a joint reading. You can adjust the list afterward.')}</p>
      <div className="reading-picker-list">{report.papers.map(paper => <label className="reading-picker-row" key={paper.paper_id}><input type="checkbox" checked={selected.includes(paper.paper_id)} onChange={() => setSelected(current => current.includes(paper.paper_id) ? current.filter(id => id !== paper.paper_id) : [...current, paper.paper_id])} /><span><strong>{paper.card.title}</strong><small>{paper.arxiv_id} · {paper.basis === 'full_pdf' ? `${paper.covered_pages.length} ${t('页全文', 'full-text pages')}` : t('仅摘要；精读需上传 PDF', 'Abstract only; upload a PDF to read')}</small></span></label>)}</div>
      <div className="reading-picker-foot"><span>{t('已选择', 'Selected')} {selected.length} {settingsValue?.ui_language === 'en' && selected.length === 1 ? 'paper' : t('篇', 'papers')}</span><button className="primary compact" disabled={!selected.length || saving} onClick={() => void addToReading()}>{t('进入精读', 'Open deep reading')} ↗</button></div>
    </section></div>}
    <main className="discovery-workspace">
      <section className="discovery-hero"><div className="hero-orbit" aria-hidden="true"><i/><i/><i/></div><p className="eyebrow">DISCOVER · UNDERSTAND · CONNECT</p><h1>{t('看见前沿，读懂进展。', 'See the frontier. Understand the progress.')}</h1><p className="subtitle">{t('从一个研究领域出发，把最新论文变成能理解、能继续读的知识。', 'Start with a research field and turn recent papers into knowledge you can understand and explore.')}</p>
        <label className="search-field"><span aria-hidden="true">⌕</span><input aria-label={t('搜索 arXiv 领域或分类', 'Search arXiv fields or categories')} placeholder={t('输入领域、分类名或代码，如 AI、机器学习、cs.AI', 'Enter a field, category, or code, such as AI or cs.AI')} value={query} disabled={busy} onChange={event => setQuery(event.target.value)} /></label>
        <p className="search-note">{t('选择官方分类后，获取截至当前时刻的最新最多 5 篇并生成速览；输入 cs.AI 等小类代码可只检索该小类。', 'Select an official category to retrieve up to five recent papers and generate an overview. A specific code such as cs.AI searches only that subcategory.')}</p>
      </section>
      {error && <div className="error-banner" role="alert"><strong>{t('操作未完成', 'Action not completed')}</strong><p>{error}</p></div>}
      {!job && !query.trim() && <section className="category-index custom-tags"><div className="panel-title"><h2>{t('我的分类标签', 'My category shortcuts')}</h2><span className="muted small">{t('在下方搜索官方分类，点 ☆ 添加', 'Search official categories below and select ☆ to add')}</span></div>
        {settingsValue?.custom_categories.length ? <div className="tag-list">{settingsValue.custom_categories.map(code => {
          const category = categories.find(item => item.code === code);
          return <div className="category-tag" key={code}><button disabled={busy} onClick={() => void start(category ?? { code } as Category)}>{settingsValue?.ui_language === 'en' ? category?.official_name ?? code : category?.zh_name ?? code} <small>{code}</small></button><button className="tag-remove" aria-label={`${t('移除', 'Remove')} ${code}`} disabled={saving} onClick={() => void toggleTag(code)}>×</button></div>;
        })}</div> : <p className="muted">{t('待添加', 'No shortcuts yet')}</p>}
      </section>}
      {!job && !query.trim() && ranking?.groups.length ? <section className="category-index"><div className="panel-title"><h2>{t('官方月度投稿排行', 'Monthly submissions by archive')}</h2><a href={ranking.source_url} target="_blank" rel="noreferrer">arXiv ↗</a></div><p className="muted small">{ranking.month} · {t('arXiv 已汇总的 Archive 月投稿量；点击大类生成速览。', 'arXiv archive-level monthly submissions. Select an archive to create an overview.')}{ranking.source_state === 'bundled_verified' && ` · ${t('已核实快照，联网后可手动更新', 'Verified snapshot; refresh online for updates')}`}</p><div className="tag-list">{ranking.groups.slice(0, rankingVisible).map(row => <button className="category-tag ranking-tag" key={row.code} disabled={busy} onClick={() => void start(row)}><strong>{settingsValue?.ui_language === 'en' ? row.official_name : row.zh_name}</strong> <small>{row.code} · {row.count.toLocaleString()}</small></button>)}</div><div className="inline-actions">{ranking.groups.length > rankingVisible && <button className="text-button" onClick={() => setRankingVisible(ranking.groups.length)}>{t('显示全部排行', 'Show all archives')}</button>}<button className="text-button" disabled={saving} onClick={() => void refreshRanking()}>{t('手动获取最新月份', 'Refresh monthly ranking')}</button></div></section> : !job && !query.trim() && ranking?.stopped && <section className="category-index"><p className="muted">{t('官方月度排行暂不可用；已停止自动获取。', 'Monthly ranking is unavailable; automatic attempts have stopped.')}</p><button className="secondary" disabled={saving} onClick={() => void refreshRanking()}>{t('手动获取', 'Try manually')}</button></section>}
      {!busy && (!report || query.trim()) && <section className="category-index"><div className="panel-title"><h2>{query.trim() ? t('匹配的官方分类', 'Matching official categories') : t('浏览学科分类', 'Browse categories')}</h2><a href="https://arxiv.org/category_taxonomy" target="_blank" rel="noreferrer">arXiv {t('分类表', 'taxonomy')} ↗</a></div>
        {searching ? <p className="muted">{t('正在匹配官方分类…', 'Finding official categories…')}</p> : !rows.length && <p className="muted">{t('未匹配到官方分类，请换一个名称或分类代码。', 'No official categories match. Try another name or code.')}</p>}
        <div className="category-grid">{!searching && rows.slice(0, visible).map(category => <div className="category-tile category-choice" key={category.code}><button className="category-open" disabled={saving} onClick={() => void start(category)}><span className="category-code">{category.code}</span><strong>{settingsValue?.ui_language === 'en' ? category.official_name : category.zh_name}</strong><span>{settingsValue?.ui_language === 'en' ? category.group : category.official_name}</span><small>{category.kind === 'archive' ? `${category.members.length} ${t('个官方子分类', 'official subcategories')}` : category.group}</small><b aria-hidden="true">↗</b></button><button className="category-star" aria-label={`${settingsValue?.custom_categories.includes(category.code) ? t('移除', 'Remove') : t('添加', 'Add')} ${category.code} ${t('标签', 'shortcut')}`} disabled={saving || !settingsValue} onClick={() => void toggleTag(category.code)}>{settingsValue?.custom_categories.includes(category.code) ? '★' : '☆'}</button></div>)}</div>
        {rows.length > visible && <button className="secondary more-categories" onClick={() => setVisible(visible + 24)}>{t('显示更多分类', 'Show more categories')}</button>}
      </section>}
      {job?.status === 'failed' && <div className="error-banner" role="alert"><strong>{job.error?.code === 'NO_PAPERS' ? t('未找到论文', 'No papers found') : t('本次速览未完成', 'Overview not completed')}</strong><p>{job.error && errorMessage(job.error, settingsValue?.ui_language)}</p><div className="inline-actions"><button className="primary compact" disabled={saving} onClick={() => void start({ code: job.category_codes[0] } as Category, true)}>{t('重新生成', 'Regenerate')}</button><button className="secondary" onClick={() => void exit()}>{t('退出', 'Exit')}</button></div></div>}
      {job && ['queued', 'running'].includes(job.status) && <section className="progress-card panel"><span className="spinner"/><h2>{t(job.phase, 'Finding papers and generating the overview…')}</h2><p>{t('官方资源 → 全文证据 → 简明讲述 → 内容核查', 'Official sources → full text → clear explanation → review')}</p><p className="muted small">{t('检索截止', 'Search cutoff')}：{new Date(job.cutoff_at).toLocaleString()} · {job.category_codes.join(', ')}</p><button className="secondary" disabled={saving} onClick={() => void exit()}>{t('退出本次生成', 'Exit this run')}</button></section>}
      {waiting && <section className="decision-panel panel"><p className="eyebrow">CHECK THE SOURCES</p><h2>{t('这些论文还没有可用全文', 'These papers have no usable full text')}</h2><p className="muted">{t('逐篇选择摘要速览或移除，全部处理后才开始生成。不会自动补齐其他论文。', 'Choose an abstract-only overview or remove each paper. Generation starts after all are resolved.')}</p>
        {failed.map(paper => <fieldset className="paper-decision" key={paper.paper_id}><legend>{paper.title}</legend><a href={paper.source_url} target="_blank" rel="noreferrer">arXiv:{paper.arxiv_id} ↗</a><p className="error-text">{paper.error && errorMessage(paper.error, settingsValue?.ui_language)}</p>
          {paper.summary.trim() && <label><input type="radio" name={paper.paper_id} checked={choices[paper.paper_id] === 'use_abstract'} onChange={() => setChoices({ ...choices, [paper.paper_id]: 'use_abstract' })} />{t('继续生成这篇，仅基于官方摘要', 'Continue using only the official abstract')}</label>}
          <label><input type="radio" name={paper.paper_id} checked={choices[paper.paper_id] === 'remove'} onChange={() => setChoices({ ...choices, [paper.paper_id]: 'remove' })} />{t('去掉这一篇', 'Remove this paper')}</label>
        </fieldset>)}
        <div className="inline-actions"><button className="primary compact" disabled={saving || failed.some(p => !choices[p.paper_id])} onClick={() => void confirm()}>{t('确认并继续', 'Confirm and continue')}</button><button className="secondary" disabled={saving} onClick={() => void exit()}>{t('退出', 'Exit')}</button></div>
      </section>}
      {languageJob && languageJob.status !== 'failed' && <div className="progress-card panel"><span className="spinner"/><p>{t('正在转换报告语言；原报告仍可阅读。', 'Converting report language; the original remains readable.')}</p></div>}
      {languageJob?.status === 'failed' && <div className="error-banner" role="alert"><strong>{t('语言转换失败', 'Language conversion failed')}</strong><p>{languageJob.error && errorMessage(languageJob.error, settingsValue?.ui_language)}</p><div className="inline-actions"><button className="primary compact" onClick={() => { setError(''); setLanguageAttempt(value => value + 1); }}>{t('重新生成', 'Regenerate')}</button><button className="secondary" onClick={() => { void updateSettings({ report_language: report?.language ?? 'zh' }); setLanguageJob(null); setError(''); }}>{t('退出', 'Exit')}</button></div></div>}
      {report && <section className="overview-output">
        {report.validation_sample && <div className="reading-review-notice"><strong>{t('开发验证样本', 'Development validation sample')}</strong><p>{t('这两篇来自同一批最新检索。它验证速览与进入精读的流程；其他论文的全文失败选择仍需在正常检索中逐篇确认。', 'These two papers came from one recent search. They validate the overview-to-reading flow; full-text failures for other papers still require a decision in a normal search.')}</p></div>}
        <div className="batch-header panel"><p className="eyebrow">THE LATEST, IN CONTEXT · {report.language === 'en' ? 'English' : report.language === 'bilingual' ? '中文 + English' : '中文'}</p><h2>{t('这批论文在推进什么', 'What is this batch advancing?')}</h2><p className="batch-intro">{report.batch.map_summary}</p><p className="batch-position"><span>{t('专业定位', 'Research context')}</span> {report.batch.shared_address.earth.name} → {report.batch.shared_address.country.name}</p><p className="muted small">{t('检索', 'Retrieved')} {report.retrieved_count} {t('篇', 'papers')} · {t('本次速览', 'Included')} {report.included_count} {t('篇', 'papers')} · {t('截至', 'As of')} {new Date(report.cutoff_at).toLocaleString()}</p>
          <div className="cluster-list">{report.batch.clusters.map(cluster => <div key={cluster.cluster_id}><strong>{cluster.name}</strong><span>{cluster.what_is_happening}</span><small>{cluster.paper_ids.length} {settingsValue?.ui_language === 'en' && cluster.paper_ids.length === 1 ? 'paper' : t('篇', 'papers')}</small></div>)}</div>
          {!!report.batch.highlights.length && <ul>{report.batch.highlights.map((highlight, index) => <li key={index}>{highlight}</li>)}</ul>}
          <p className="muted small">{t('分组、关联与星级是本批论文的 AI 阅读建议。每篇保留原始 arXiv 分类，精读材料由你自行选择。', 'Groups, connections, and ratings are AI reading suggestions. Original arXiv categories remain visible; you choose the papers for deep reading.')}</p>
          {report.batch.reading_order && <p className="muted small">{t('建议阅读顺序', 'Suggested reading order')}{t('：', ': ')}{report.batch.reading_order.join(' → ')}{t('。', '.')}</p>}
        </div>
        {report.papers.map((paper, index) => <article className="overview-card panel" key={paper.paper_id}>
          <header><span className="section-number">{String(index+1).padStart(2, '0')}</span><span className={`basis-pill ${paper.basis === 'abstract' ? 'abstract' : ''}`}>{paper.basis === 'abstract' ? t('仅基于摘要', 'Abstract only') : `${t('全文', 'Full text')} · ${paper.covered_pages.length} ${t('页', 'pages')}`}</span></header>
          <h3>{paper.card.title}</h3>
          {visualFor(paper) && <figure className="overview-visual">
            <picture>
              {!visualFor(paper).svg_zh && visualFor(paper).theme.endsWith('-scene') && <source media="(max-width: 650px)" srcSet={`/overview-visuals/${visualFor(paper).theme}-preview.svg`} />}
              <img src={visualSrc(paper, report.language === 'en' ? 'en' : 'zh')} alt={report.language === 'en' ? visualFor(paper).caption_en : visualFor(paper).caption_zh} loading="lazy" />
            </picture>
            <figcaption><span>{report.language === 'en' ? visualFor(paper).caption_en : report.language === 'bilingual' ? `${visualFor(paper).caption_zh} / ${visualFor(paper).caption_en}` : visualFor(paper).caption_zh}</span><small>{t('概念示意 · 非论文原图或结果图', 'Concept illustration · Not a figure or measured result from the paper')}</small></figcaption>
            {report.language === 'bilingual' && visualFor(paper).svg_en && <img src={visualSrc(paper, 'en')} alt={visualFor(paper).caption_en} loading="lazy" />}
            {!visualFor(paper).svg_zh && visualFor(paper).theme.endsWith('-scene') && <details className="overview-visual-steps"><summary>{t('展开三步大图', 'Open the three-step illustration')}</summary><img src={`/overview-visuals/${visualFor(paper).theme}-mobile.svg`} alt={settingsValue?.ui_language === 'en' ? visualFor(paper).caption_en : visualFor(paper).caption_zh} loading="lazy" /></details>}
          </figure>}
          {paper.card.plain && <div className="card-plain"><strong>{t('先看懂', 'In plain language')}</strong><div>{markdown(paper.card.plain, 'plain', paper.paper_id)}</div></div>}<p className="original-title"><a href={paper.source_url} target="_blank" rel="noreferrer">{paper.title} ↗</a></p><p className="small muted">arXiv:{paper.arxiv_id} · {t('首次投稿', 'First submitted')} {new Date(paper.published_at).toLocaleDateString()} · {paper.categories.join(' / ')}</p>
          {paper.source_warnings?.map((warning, i) => <p className="small muted" key={i}>{warning}</p>)}
          {paper.basis === 'abstract' && <div className="reading-review-notice"><strong>{t('全文未获取或解析成功', 'Full text unavailable or unreadable')}</strong><p>{paper.error && errorMessage(paper.error, settingsValue?.ui_language)}。{t('你已选择按摘要生成；精读仍需完整正文。', 'You chose an abstract-only overview; deep reading still needs the complete paper.')}</p></div>}
          <div className="card-position learning-markdown"><strong>{t('研究定位', 'Research context')}</strong>{markdown(paper.card.address, 'address', paper.paper_id)}</div><div className="card-one-liner"><strong>{t('专业说法', 'Technical summary')}</strong>{markdown(paper.card.one_liner, '', paper.paper_id)}</div><p className="card-tags">{researchWording(paper.card.tags, 'quick_card')}</p>
          {report.batch.ratings.find(row => row.arxiv_id === paper.paper_id) && <p className="muted small">{t('精读建议', 'Reading suggestion')}{t('：', ': ')}{report.batch.ratings.find(row => row.arxiv_id === paper.paper_id)?.stars} {t('星', 'stars')} · {report.batch.ratings.find(row => row.arxiv_id === paper.paper_id)?.reason}</p>}
          {report.audit.results.find(row => row.arxiv_id === paper.paper_id)?.issues.filter(issue => (issue.severity === 'medium' || issue.severity === 'high') && !report.audit_adjudications?.some(item => item.arxiv_id === paper.paper_id && item.check === issue.check && item.location === issue.location)).map((issue, i) => <div className="reading-review-notice" key={i}><strong>{t('待核查提示', 'Review note')}</strong><p>{issue.problem}</p><p>{issue.fix}</p></div>)}
          <details className="card-expand"><summary>{t('展开：麻烦、妙招、效果与边界', 'Expand: problem, idea, results, and limits')}</summary>{([['pain', '麻烦', 'Problem'], ['trick', '妙招', 'Key idea'], ['result', '效果', 'Result'], ['so_what', '意义', 'Why it matters'], ['caveat', '冷静一下', 'Caveat']] as const).map(([key, label, english]) => <div className="card-detail learning-markdown" key={key}><h4>{t(label, english)}</h4>{markdown(paper.card[key], '', paper.paper_id)}</div>)}
            <div className="card-sources"><h4>{t('回看来源', 'Check sources')}</h4>{paper.evidence.filter(e => paper.card.evidence_ids.includes(e.evidence_id)).map(e => <details className="citation" id={`overview-${paper.paper_id}-${e.evidence_id}`} key={e.evidence_id}><summary>{e.evidence_id} · {e.source_type === 'arxiv_abstract' ? t('官方摘要', 'Official abstract') : `${t('PDF 物理页', 'PDF pages')} ${e.pdf_page_start}–${e.pdf_page_end_inclusive}`}</summary><blockquote>{e.source_text}</blockquote><a href={e.source_type === 'arxiv_abstract' ? paper.source_url : `https://arxiv.org/pdf/${paper.arxiv_id}#page=${e.pdf_page_start}`} target="_blank" rel="noreferrer">{t('查看原文', 'Open source')} ↗</a></details>)}</div>
          </details>
        </article>)}
        <p className="muted small">{t('本次自动核查', 'Automated review')} {report.audit_rounds} {t('轮', 'rounds')}{t('；', '; ')}{t('来源位置已校验，内容仍可对照原文复核。', 'Source locations were checked; please verify claims against the paper.')}</p>
      </section>}
    </main><footer className="footer">AI Radar · {t('学习，从发现开始。', 'Learning starts with discovery.')}<span>{t('论文与报告仅保留在当前本机服务会话', 'Papers and reports stay in this local service session')}</span></footer>
  </>;
}
