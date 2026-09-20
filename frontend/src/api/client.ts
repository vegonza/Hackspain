export const API_BASE = '/api'

async function baseFetch(url: string, options: RequestInit): Promise<Response> {
  try {
    const response = await fetch(`${API_BASE}${url}`, options)
    if (!response.ok) {
      if (response.status >= 500 || !response.headers.get('content-type')?.includes('application/json')) {
        throw new Error(i18n.t('invoices.requestFailed'))
      }
      const error: { detail: unknown } = await response.json()
      const message = error.detail === 'supplier_has_orders'
        ? i18n.t('suppliers.hasOrders')
        : error.detail === 'order_exists'
        ? i18n.t('orders.exists')
        : error.detail === 'order_not_found'
          ? i18n.t('orders.notFound')
        : error.detail === 'order_supplier_not_found'
          ? i18n.t('orders.supplierNotFound')
        : error.detail === 'supplier_exists'
        ? i18n.t('suppliers.exists')
        : error.detail === 'supplier_not_found'
          ? i18n.t('suppliers.notFound')
        : error.detail === 'invalid_pdf'
        ? i18n.t('invoices.invalidPdf')
        : error.detail === 'unsupported_file_type'
          ? i18n.t('invoices.unsupportedFileType')
        : error.detail === 'conversion_failed'
          ? i18n.t('invoices.conversionFailed')
        : error.detail === 'invoice_processing'
          ? i18n.t('invoices.processingConflict')
        : error.detail === 'invalid_saved_extraction'
          ? i18n.t('invoices.invalidSavedExtraction')
        : error.detail === 'duplicate_pdf'
          ? i18n.t('invoices.duplicatePdf')
          : error.detail === 'extraction_failed'
            ? i18n.t('invoices.extractionFailed')
          : i18n.t('invoices.requestFailed')
      throw new Error(message)
    }
    return response
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    toast.error(error instanceof Error && !(error instanceof TypeError) && !(error instanceof SyntaxError)
      ? error.message
      : i18n.t('invoices.requestFailed'))
    throw error
  }
}

export async function fetchJson<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await baseFetch(url, options)
  return response.json()
}

import i18n from '@/i18n'
import { toast } from 'sonner'

export async function fetchEmpty(url: string, options: RequestInit): Promise<void> {
  await baseFetch(url, options)
}

export async function fetchBlob(url: string, options: RequestInit = {}): Promise<Blob> {
  const response = await baseFetch(url, options)
  return response.blob()
}
