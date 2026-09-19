import { Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { useSearchInput } from '@/hooks/useSearchInput'
import { cn } from '@/lib/utils'

interface SearchInputProps {
  value: string
  onChange: (value: string) => void
  placeholder: string
  className?: string
  autoFocus?: boolean
  isLoading?: boolean
  collapsible?: boolean
  onCollapsedOpenChange?: (open: boolean) => void
}

export function SearchInput({
  value,
  onChange,
  placeholder,
  className,
  autoFocus,
  isLoading = false,
  collapsible = true,
  onCollapsedOpenChange,
}: SearchInputProps) {
  const {
    collapsed,
    forcedOpen,
    rootRef,
    inputRef,
    openCollapsed,
    closeCollapsed,
    handleKeyDown,
  } = useSearchInput(collapsible)
  return (
    <div
      ref={rootRef}
      className={cn(
        'flex h-8 min-w-0 max-w-[30rem] items-center',
        collapsed && !forcedOpen ? 'w-8 flex-none' : 'flex-1',
        className,
      )}
    >
      <div className={cn('relative w-full', collapsed && !forcedOpen && 'hidden')}>
        {isLoading ? (
          <Skeleton className="h-8 w-full rounded-lg" />
        ) : (
          <>
            <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              ref={inputRef}
              autoFocus={autoFocus}
              value={value}
              onChange={(event) => onChange(event.target.value)}
              onBlur={(event) => {
                closeCollapsed(event)
                if (onCollapsedOpenChange !== undefined) onCollapsedOpenChange(false)
              }}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              aria-label={placeholder}
              className="h-8 pl-8 text-base focus-visible:border-input focus-visible:ring-0 md:text-sm"
            />
          </>
        )}
      </div>
      {collapsed && !forcedOpen && (
        isLoading ? (
          <Skeleton className="size-8 shrink-0 rounded-lg" />
        ) : (
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => {
              openCollapsed()
              if (onCollapsedOpenChange !== undefined) onCollapsedOpenChange(true)
            }}
            aria-label={placeholder}
            className={cn(
              'shrink-0 text-foreground hover:text-foreground',
              value !== '' && 'text-blue-700 hover:text-blue-700 dark:text-blue-300 dark:hover:text-blue-300',
            )}
          >
            <Search className="size-4" />
          </Button>
        )
      )}
    </div>
  )
}
