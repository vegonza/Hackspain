export const invoiceFileExtensions = ['.pdf', '.doc', '.docx', '.odt', '.rtf', '.ppt', '.pptx', '.odp', '.xls', '.xlsx', '.ods']
export const invoiceFileAccept = invoiceFileExtensions.join(',')

export function isSupportedInvoiceFile(name: string): boolean {
  return invoiceFileExtensions.some(extension => name.toLowerCase().endsWith(extension))
}
