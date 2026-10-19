import { ReadingPage } from './pages/ReadingPage';
import { DiscoveryPage } from './pages/DiscoveryPage';
import { useEffect, useState } from 'react';
import { UiProvider, useUi } from './i18n';
function AppBody() {
  const { settings, t } = useUi();
  const readingAnchor = () => ['#reading', '#evidence-', '#concept-'].some(prefix => location.hash.startsWith(prefix));
  const [reading, setReading] = useState(readingAnchor);
  const [opening, setOpening] = useState(true);
  useEffect(() => { const route = () => setReading(readingAnchor()); window.addEventListener('hashchange', route); return () => window.removeEventListener('hashchange', route); }, []);
  useEffect(() => { const timer = window.setTimeout(() => setOpening(false), 2000); return () => window.clearTimeout(timer); }, []);
  const go = (value: boolean) => { location.hash = value ? 'reading' : 'home'; setReading(value); window.scrollTo(0, 0); };
  useEffect(() => { document.title = settings?.ui_language === 'en' ? 'AI Radar · Discover & Read' : 'AI Radar · 发现与精读'; }, [settings?.ui_language]);
  return <>
    {reading ? <ReadingPage onHome={() => go(false)} /> : <DiscoveryPage onReading={() => go(true)} />}
    {opening && <button className="opening-screen" onClick={() => setOpening(false)} aria-label={t('跳过开场，进入 AI Radar', 'Skip intro and enter AI Radar')}>
      <span className="opening-art" aria-hidden="true"><i/><i/><i/><b>◎</b></span>
      <span className="opening-wordmark">AI <strong>Radar</strong></span>
      <span className="opening-caption">{t('看见前沿，读懂进展。', 'See the frontier. Understand the progress.')}</span>
      <span className="opening-skip">{t('点击任意位置跳过', 'Click anywhere to skip')} ↗</span>
    </button>}
  </>;
}
export default function App() { return <UiProvider><AppBody /></UiProvider>; }
