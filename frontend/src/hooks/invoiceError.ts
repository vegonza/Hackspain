export function invoiceErrorKey(error: string | null) {
  if (error === 'openrouter_key_limit_exceeded') return 'invoices.openrouterKeyLimit'
  if (error === 'PermissionDeniedError (HTTP 403)') return 'invoices.providerAccessDenied'
  return 'invoices.error'
}
