export function formatAmount(amount: number, currency: string): string {
  return new Intl.NumberFormat('es-ES', currency === '' ? {} : { style: 'currency', currency }).format(amount)
}

export function formatStatus(status: string): string {
  return status.charAt(0).toLocaleUpperCase('es-ES') + status.slice(1).toLocaleLowerCase('es-ES')
}

export function formatDateLong(iso: string, locale: string): string {
  const date = new Date(iso)
  const formattedDate = date.toLocaleDateString(locale, { day: 'numeric', month: 'short', year: 'numeric' })
  const formattedTime = date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', hour12: false })
  return `${formattedDate}, ${formattedTime}`
}
