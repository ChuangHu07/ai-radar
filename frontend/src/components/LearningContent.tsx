import { useState } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import type { KnowledgeConcept } from '../api/types';
import { researchWording } from './researchWording';
import { useUi } from '../i18n';

export function LearningMarkdown({ text, sectionKey }: { text: string; sectionKey: string }) {
  // Some JSON model outputs double-escape every TeX command. Decode only
  // command escapes inside math; retain normal TeX and matrix row breaks.
  const mathReady = researchWording(text, sectionKey).replace(/\$\$[\s\S]*?\$\$|\$[^$\n]+\$/g, math => /(?<!\\)\\[A-Za-z]/.test(math)
    ? math : math.replace(/\\\\(?=[A-Za-z,;!{}])/g, '\\'));
  const linked = mathReady.replace(/\[(E\d{4})\]/g, (_, id: string) => `[${id}](#evidence-${sectionKey}-${id})`);
  return <div className="learning-markdown"><Markdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[[rehypeKatex, { strict: 'ignore', trust: false }]]}
    components={{ a: ({ href, children }) => href?.startsWith('#evidence-') ? <a href={href}>{children}</a> : <span>{children}</span> }} skipHtml>{linked}</Markdown></div>;
}

export function LearningNarrative({ text, sectionKey }: { text: string; sectionKey: string }) {
  const { t } = useUi();
  if (sectionKey !== 'core_idea') return <LearningMarkdown text={text} sectionKey={sectionKey} />;
  const split = text.split(/^### (?:技术版|Technical version)\s*$/mi);
  return <><LearningMarkdown text={split[0]} sectionKey={sectionKey} />{split.length > 1 && <details className="technical-layer"><summary>{t('展开技术版', 'Expand technical explanation')}</summary><LearningMarkdown text={split.slice(1).join('\n')} sectionKey={sectionKey} /></details>}</>;
}

function KnowledgeText({ text, language, markdown = false }: { text: string; language: 'zh' | 'en' | 'bilingual'; markdown?: boolean }) {
  const parts = language === 'bilingual' ? text.split('\n\nEnglish: ', 2) : [text];
  if (parts.length !== 2) return markdown ? <LearningMarkdown text={text} sectionKey="knowledge" /> : <>{text}</>;
  if (markdown) return <div className="bilingual-card-text"><div lang="zh"><LearningMarkdown text={parts[0]} sectionKey="knowledge" /></div><div lang="en"><strong>English</strong><LearningMarkdown text={parts[1]} sectionKey="knowledge" /></div></div>;
  return <span className="bilingual-card-text"><span lang="zh">{parts[0]}</span><span lang="en"><strong>English</strong>{parts[1]}</span></span>;
}

export function KnowledgeCards({ concepts, language = 'zh' }: { concepts: KnowledgeConcept[]; language?: 'zh' | 'en' | 'bilingual' }) {
  const { t } = useUi();
  const [known, setKnown] = useState<string[]>([]);
  return <div className="knowledge-cards">{concepts.map(item => <article key={item.id} id={`concept-${item.id}`} className={`knowledge-card ${known.includes(item.id) ? 'known' : ''}`}>
    <header><h4>{item.id} · {item.level} · <KnowledgeText text={item.term} language={language} /> {language !== 'en' && <span className="muted">{item.en}</span>}</h4>
      {item.level !== 'L3' && <button className="text-button" onClick={() => setKnown(old => old.includes(item.id) ? old.filter(id => id !== item.id) : [...old, item.id])}>{known.includes(item.id) ? t('重新复习', 'Review again') : t('我会了，跳过', 'I know this, skip')}</button>}</header>
    {!known.includes(item.id) && <>{item.level === 'L3' ? <p>{t('本文的新概念，沿着核心思想与方法中的概念卡学习。', 'A new concept in this paper; learn it through the core idea and method cards.')}</p> : <>
      <p><strong>{t('为什么需要', 'Why it matters')}：</strong><KnowledgeText text={item.why_needed} language={language} /></p><p className="enough-standard"><strong>{t('学到这里就够用', 'What is enough to know')}：</strong><KnowledgeText text={item.enough_standard} language={language} /></p>
      {item.quick_explain && <KnowledgeText text={item.quick_explain} language={language} markdown />}
      <p><strong>{t('自检题', 'Self-check')}：</strong><KnowledgeText text={item.self_check.q} language={language} /></p><details className="quiz-answer"><summary>{t('查看参考答案', 'Show answer')}</summary><KnowledgeText text={item.self_check.a} language={language} markdown /></details>
      {item.depends_on.length > 0 && <p className="small">{t('先备好', 'Prepare first')}：{item.depends_on.map((id, i) => <span key={id}>{i > 0 && ' → '}<a href={`#concept-${id}`}>{id}</a></span>)}</p>}
      {item.learn_from.length > 0 && <details className="learning-resources"><summary>{t('学习途径与检索关键词', 'Learning resources and search terms')}</summary><ul>{item.learn_from.map((resource, i) => <li key={i}><KnowledgeText text={resource} language={language} /></li>)}</ul></details>}
    </>}</>}
  </article>)}</div>;
}
