import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(num: number): string {
  return new Intl.NumberFormat().format(num);
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
  }).format(amount);
}

export function formatPercentage(value: number, decimals = 1): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(decimals)}%`;
}

export function getPositionColor(position: string): string {
  const colors: Record<string, string> = {
    QB: "text-red-500",
    RB: "text-green-500",
    WR: "text-blue-500",
    TE: "text-amber-500",
  };
  return colors[position] || "text-gray-500";
}

export function getTrendColor(trend: number): string {
  if (trend > 0) return "text-green-500";
  if (trend < 0) return "text-red-500";
  return "text-gray-500";
}
