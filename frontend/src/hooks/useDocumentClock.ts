import { useSyncExternalStore } from 'react'

function subscribe(listener: () => void): () => void {
  const timer = setInterval(listener, 1000)
  return () => clearInterval(timer)
}

function idle(): () => void {
  return () => {}
}

function currentSecond(): number {
  return Math.floor(Date.now() / 1000) * 1000
}

export function elapsedMilliseconds(createdAt: string, finishedAt: string | null, running: boolean, now: number): number | null {
  const end = running ? now : finishedAt === null ? null : Date.parse(finishedAt)
  return end === null ? null : Math.max(0, end - Date.parse(createdAt))
}

export function useDocumentClock(running: boolean): number {
  return useSyncExternalStore(running ? subscribe : idle, currentSecond)
}
