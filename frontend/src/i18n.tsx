import { createContext, useContext, useEffect, useState } from 'react';
import { request, RequestError } from './api/client';
import type { ApiError, UserSettings } from './api/types';

const errorsEn: Record<string, string> = {
  NO_PAPERS: 'No papers were found in this official category.',
  SOURCE_UNAVAILABLE: 'The arXiv source could not be reached. Check your connection and retry.',
  SOURCE_TIMEOUT: 'The arXiv request timed out.',
  SOURCE_FORMAT_CHANGED: 'The arXiv source format could not be read.',
  SOURCE_PDF_URL_INVALID: 'The paper PDF link is not a valid arXiv source.',
  PDF_TOO_LARGE: 'This PDF exceeds the 50 MiB limit.',
  PDF_ENCRYPTED: 'This PDF is password-protected. Upload an unlocked copy.',
  PDF_PAGE_LIMIT: 'This PDF exceeds the 150-page limit.',
  PDF_UNREADABLE: 'The PDF could not be parsed. Replace or remove this paper.',
  PDF_NO_TEXT: 'The PDF has no extractable text. Scanned PDFs are not supported.',
  NO_USABLE_PAPERS: 'No usable papers remain in this overview.',
  SOURCE_COVERAGE_INCOMPLETE: 'The complete paper could not be covered; the report was not published.',
  MATERIALS_NOT_READY: 'Resolve every failed paper before generating a report.',
  MODEL_NOT_CONFIGURED: 'Configure the selected model API key in your local .env file.',
  MODEL_BUDGET_LIMIT: 'The development validation budget has been reached.',
  MODEL_UNAVAILABLE: 'The model service is unavailable or timed out.',
  MODEL_OUTPUT_INVALID: 'The model output did not pass structural or factual checks.',
  LANGUAGE_OUTPUT_INVALID: 'The language version changed a required format, citation, number, or formula. The original report remains available.',
  REPORT_QUALITY_FAILED: 'The report did not pass the source and quality review.',
  SERVICE_UNAVAILABLE: 'The local processing service is unavailable. Start the backend and retry.',
  REVISION_CONFLICT: 'This item changed in another page. Refresh and retry.',
};

export function errorMessage(error: unknown, language?: UserSettings['ui_language']) {
  const detail: ApiError | undefined = error instanceof RequestError ? error.detail
    : error && typeof error === 'object' && 'code' in error ? error as ApiError : undefined;
  if (language !== 'en') return detail?.details ?? (error as Error)?.message ?? '操作未完成。';
  if (detail) {
    const numberFailure = detail.details?.match(/^速览结果数字未在该栏引用的原文中核对[：:]\s*(.+)$/);
    if (detail.code === 'MODEL_OUTPUT_INVALID' && numberFailure)
      return `A result number could not be verified in the evidence cited for this section: ${numberFailure[1]}.`;
    return errorsEn[detail.code] ?? `Request failed (${detail.code}).`;
  }
  return 'The request could not be completed. Please retry.';
}

type UiContextValue = { settings: UserSettings | null; update: (values: Partial<UserSettings>) => Promise<void>; t: (zh: string, en: string) => string };
const UiContext = createContext<UiContextValue | null>(null);

export function UiProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  useEffect(() => { void request<UserSettings>('/settings').then(setSettings).catch(() => {}); }, []);
  async function update(values: Partial<UserSettings>) {
    if (!settings) return;
    try {
      const next = await request<UserSettings>('/settings', { method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expected_revision: settings.revision, ...values }) });
      setSettings(next);
    } catch (error) {
      void request<UserSettings>('/settings').then(setSettings).catch(() => {});
      throw error;
    }
  }
  const t = (zh: string, en: string) => settings?.ui_language === 'en' ? en : zh;
  return <UiContext.Provider value={{ settings, update, t }}>{children}</UiContext.Provider>;
}

export function useUi() {
  const value = useContext(UiContext);
  if (!value) throw new Error('Missing UiProvider');
  return value;
}

export function LanguageControls() {
  const { settings, update, t } = useUi();
  const [error, setError] = useState('');
  if (!settings) return null;
  return <div className="language-controls">
    <label>{t('界面', 'Interface')} <select aria-label={t('界面语言', 'Interface language')} value={settings.ui_language}
      onChange={event => { setError(''); void update({ ui_language: event.target.value as UserSettings['ui_language'] }).catch(err => setError(errorMessage(err, settings.ui_language))); }}>
      <option value="zh">中文</option><option value="en">English</option>
    </select></label>
    <label>{t('报告', 'Report')} <select aria-label={t('报告语言', 'Report language')} value={settings.report_language}
      onChange={event => { setError(''); void update({ report_language: event.target.value as UserSettings['report_language'] }).catch(err => setError(errorMessage(err, settings.ui_language))); }}>
      <option value="zh">中文</option><option value="en">English</option><option value="bilingual">中文 + English</option>
    </select></label>
    {error && <span role="alert" className="error-text">{error}</span>}
  </div>;
}
