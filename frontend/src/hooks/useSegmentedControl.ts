import { useCallback } from 'react'

export function useSegmentedControl<TValue extends string>(onValueChange: (value: TValue) => void) {
  return useCallback((value: string): void => {
    if (value !== '') onValueChange(value as TValue)
  }, [onValueChange])
}
