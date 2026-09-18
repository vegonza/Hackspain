import { fetchJson } from './client'

export interface ExampleResponse {
  status: 'ok'
  service: 'FastAPI'
}

export function fetchExample(): Promise<ExampleResponse> {
  return fetchJson<ExampleResponse>('/example')
}
