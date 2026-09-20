export const API_BASE = '/api'

export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(message: string, status: number, detail: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function baseFetch(url: string, options: RequestInit): Promise<Response> {
  try {
    const response = await fetch(`${API_BASE}${url}`, options)
    if (!response.ok) {
      if (response.status >= 500 || !response.headers.get('content-type')?.includes('application/json')) {
        throw new Error(i18n.t('invoices.requestFailed'))
      }
      const error: { detail: unknown } = await response.json()
      const message = typeof error.detail === 'string' && error.detail.startsWith('verifactu_test_rejected: ')
        ? i18n.t('issued.errors.testRejectedDetail', { reason: error.detail.slice('verifactu_test_rejected: '.length) })
        : typeof error.detail === 'string' && error.detail in billingErrors
        ? i18n.t(billingErrors[error.detail])
        : error.detail === 'supplier_has_orders'
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
      throw new ApiError(message, response.status, error.detail)
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

import type { ParseKeys } from 'i18next'
import i18n from '@/i18n'
import { toast } from 'sonner'

export async function fetchEmpty(url: string, options: RequestInit): Promise<void> {
  await baseFetch(url, options)
}

export async function fetchBlob(url: string, options: RequestInit = {}): Promise<Blob> {
  const response = await baseFetch(url, options)
  return response.blob()
}

export async function fetchStatus(url: string, options: RequestInit = {}): Promise<number> {
  try {
    return (await fetch(`${API_BASE}${url}`, options)).status
  } catch (error) {
    toast.error(i18n.t('invoices.requestFailed'))
    throw error
  }
}

const billingErrors: Record<string, ParseKeys> = {
  invoice_not_reviewable: 'invoices.resolutionConflict',
  invoice_duplicate_payment: 'invoices.resolutionDuplicate',
  invoice_identity_required: 'invoices.resolutionIdentity',
  gestoria_not_configured: 'gestoria.errors.notConfigured',
  gestoria_busy: 'gestoria.errors.busy',
  gestoria_file_too_large: 'gestoria.errors.fileTooLarge',
  gestoria_send_failed: 'gestoria.errors.failed',
  gestoria_send_uncertain: 'gestoria.errors.uncertain',
  gestoria_send_expired: 'gestoria.errors.expired',
  gestoria_pending_send: 'gestoria.errors.pending',
  verifactu_test_only: 'issued.errors.testOnly',
  verifactu_test_pending: 'issued.errors.testPending',
  verifactu_test_failed: 'issued.errors.testFailed',
  verifactu_test_rejected: 'issued.errors.testRejected',
  issued_invoice_locked: 'issued.errors.locked',
  billing_company_required: 'issued.errors.companyRequired',
  billing_client_exists: 'issued.errors.clientExists',
  billing_client_not_found: 'issued.errors.clientMissing',
  billing_client_has_invoices: 'clients.hasInvoices',
  issued_invoice_not_found: 'issued.errors.missing',
  issued_invoice_pdf_pending: 'issued.errors.pdfPending',
}
