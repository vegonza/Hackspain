import * as React from "react"
import type { VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { Tooltip } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { buttonVariants } from "@/lib/button-variants"

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  title,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
}) {
  const Comp = asChild ? Slot.Root : "button"

  const button = (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )

  return typeof title === "string"
    ? <Tooltip text={title} asChild>{button}</Tooltip>
    : button
}

export { Button }
