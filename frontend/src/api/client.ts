import type { ApiError } from './types';

export class RequestError extends Error {
  constructor(public detail: ApiError) { super(detail.details); }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try { response = await fetch(`/api/v1${path}`, init); }
  catch { throw new RequestError({ code: 'SERVICE_UNAVAILABLE', message_key: 'SERVICE_UNAVAILABLE', details: '无法连接本机处理服务，请确认后端已启动。', retryable: true }); }
  let envelope;
  try { envelope = await response.json(); }
  catch { throw new Error('本机处理服务返回了无法识别的响应。'); }
  if (!response.ok) throw new RequestError(envelope.error ?? { code: 'SERVICE_ERROR', details: '本机处理服务异常。' });
  return envelope.data as T;
}

export function jsonPost<T>(path: string, body: unknown, idempotency?: string) {
  return request<T>(path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(idempotency ? { 'Idempotency-Key': idempotency } : {}) }, body: JSON.stringify(body) });
}
