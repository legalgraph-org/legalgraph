/**
 * Button styles. primary: the
 * call to action (CTA gradient). solid: the primary colour, for secondary actions.
 */
export type ButtonVariant = "primary" | "solid" | "secondary" | "outline" | "ghost" | "link";
export type ButtonSize = "sm" | "md" | "lg";

const BASE =
  "no-underline inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-medium transition " +
  "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 " +
  "disabled:pointer-events-none disabled:opacity-50";

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: "bg-cta-gradient text-white! shadow-xs hover:opacity-90",
  solid: "bg-primary text-primary-foreground! shadow-xs hover:bg-primary/90",
  secondary: "bg-secondary text-secondary-foreground! shadow-xs hover:bg-secondary/80",
  outline: "border bg-background text-foreground! shadow-xs hover:bg-muted",
  ghost: "text-foreground! hover:bg-muted",
  link: "text-primary! underline-offset-4 hover:underline",
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

export function buttonClasses(variant: ButtonVariant, size: ButtonSize, extra?: string): string {
  return [BASE, VARIANT_CLASSES[variant], SIZE_CLASSES[size], extra].filter(Boolean).join(" ");
}
