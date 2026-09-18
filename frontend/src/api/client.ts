export const API_BASE = '/api'

async function baseFetch(url: string, options: RequestInit): Promise<Response> {
  const response = await fetch(`${API_BASE}${url}`, options)

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  return response
}

export async function fetchJson<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await baseFetch(url, options)
  return response.json()
}
