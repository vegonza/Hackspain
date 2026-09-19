import type { ComponentProps } from 'react'
import { X } from 'lucide-react'
import { Dialog as DialogPrimitive } from 'radix-ui'
import { cn } from '@/lib/utils'

export function DialogContent({ className, children, closeLabel, ...props }: ComponentProps<typeof DialogPrimitive.Content> & { closeLabel: string }) {
  return <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />
    <DialogPrimitive.Content
      className={cn('fixed left-1/2 top-1/2 z-50 flex max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 flex-col gap-6 overflow-y-auto rounded-lg border bg-background p-6 text-foreground shadow-lg', className)}
      {...props}
    >
      {children}
      <DialogPrimitive.Close aria-label={closeLabel} className="absolute right-4 top-4 flex size-8 items-center justify-center rounded-sm opacity-70 transition-opacity hover:bg-muted hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <X className="size-4" />
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
}
