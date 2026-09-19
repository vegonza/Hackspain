import type * as React from "react"
import { cn } from "@/lib/utils"

export function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return (
    <thead
      data-slot="table-header"
      className={cn("bg-muted dark:bg-selected [&_tr]:border-b", className)}
      {...props}
    />
  )
}
