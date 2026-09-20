import { fetchStatus } from '@/api/client'


export async function hasSession(): Promise<boolean> {
  return await fetchStatus('/auth/session') === 204
}


export async function login(password: string): Promise<number> {
  return await fetchStatus('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  })
}
