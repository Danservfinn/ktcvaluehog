import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground",
        outline:
          "border-border text-foreground",
        // Premium variants
        premium:
          "border-transparent bg-gradient-to-r from-amber-500 to-yellow-400 text-black font-bold shadow-sm",
        accent:
          "border-transparent bg-accent text-accent-foreground",
        // Status variants - Light theme friendly
        success:
          "border-emerald-300 bg-emerald-100 text-emerald-700",
        warning:
          "border-amber-300 bg-amber-100 text-amber-700",
        error:
          "border-rose-300 bg-rose-100 text-rose-700",
        info:
          "border-sky-300 bg-sky-100 text-sky-700",
        // Trend variants
        up:
          "border-emerald-300 bg-emerald-100 text-emerald-700",
        down:
          "border-rose-300 bg-rose-100 text-rose-700",
        // Position badges - Light theme friendly
        qb:
          "border-amber-300 bg-amber-100 text-amber-700",
        rb:
          "border-emerald-300 bg-emerald-100 text-emerald-700",
        wr:
          "border-sky-300 bg-sky-100 text-sky-700",
        te:
          "border-purple-300 bg-purple-100 text-purple-700",
        pk:
          "border-pink-300 bg-pink-100 text-pink-700",
        def:
          "border-orange-300 bg-orange-100 text-orange-700",
        // Tier badges
        free:
          "border-slate-300 bg-slate-100 text-slate-600",
        pro:
          "border-transparent bg-gradient-to-r from-cyan-500 to-blue-500 text-white shadow-sm",
        elite:
          "border-transparent bg-gradient-to-r from-amber-500 via-yellow-400 to-amber-500 text-black font-bold shadow-md shadow-amber-200/50",
        // Glass variant
        glass:
          "border-border/60 bg-white/70 backdrop-blur-sm text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
