export const API_BASE = '/api'

async function baseFetch(url: string, options: RequestInit): Promise<Response> {
  try {
    const response = await fetch(`${API_BASE}${url}`, options)
    if (!response.ok) {
      const error: { detail: unknown } = await response.json()
      const message = error.detail === 'invalid_pdf'
        ? i18n.t('documents.invalidPdf')
        : error.detail === 'ocr_failed'
          ? i18n.t('documents.ocrFailed')
          : i18n.t('documents.requestFailed')
      throw new Error(message)
    }
    return response
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    toast.error(error instanceof Error && !(error instanceof TypeError)
      ? error.message
      : i18n.t('documents.requestFailed'))
    throw error
  }
}

export async function fetchJson<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await baseFetch(url, options)
  return response.json()
}

import i18n from '@/i18n'
import { toast } from 'sonner'
