"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  LayoutDashboard,
  Users,
  ArrowLeftRight,
  LineChart,
  MessageSquare,
  Settings,
  Menu,
  X,
  Sparkles,
  ChevronRight,
  LogOut,
  LogIn,
  User,
  Shield,
  Bot,
  Trophy,
} from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/contexts/auth-context";

// Thoth Logo Component
function ThothLogo({ size = "default" }: { size?: "default" | "small" }) {
  const dimensions = size === "small" ? "h-8 w-8" : "h-10 w-10";
  const iconSize = size === "small" ? "h-5 w-5" : "h-6 w-6";

  return (
    <div
      className={`${dimensions} rounded-xl bg-gradient-to-br from-amber-400 via-yellow-400 to-amber-500 flex items-center justify-center shadow-lg shadow-amber-500/25 thoth-logo`}
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        className={`${iconSize} text-black`}
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 2L2 7l10 5 10-5-10-5z" />
        <path d="M2 17l10 5 10-5" />
        <path d="M2 12l10 5 10-5" />
      </svg>
    </div>
  );
}

// Miller's Law: 7 navigation items (within 7±2 optimal range)
const navItems = [
  {
    href: "/home",
    matchPath: "/home",
    exactMatch: true,
    label: "Dashboard",
    icon: LayoutDashboard,
    description: "Overview & insights",
  },
  {
    href: "/rankings",
    matchPath: "/rankings",
    label: "Players",
    icon: Users,
    description: "Search & research",
  },
  {
    href: "/trade",
    matchPath: "/trade",
    label: "Trade",
    icon: ArrowLeftRight,
    description: "Trade analyzer",
  },
  {
    href: "/league",
    matchPath: "/league",
    label: "League",
    icon: Trophy,
    tier: "elite",
    description: "Sleeper analysis",
  },
  {
    href: "/projections",
    matchPath: "/projections",
    label: "Projections",
    icon: LineChart,
    tier: "elite",
    description: "ML predictions",
  },
  {
    href: "/ml-monitor",
    matchPath: "/ml-monitor",
    label: "ML Monitor",
    icon: Bot,
    tier: "elite",
    description: "Autonomous ML",
  },
  {
    href: "/chat",
    matchPath: "/chat",
    label: "Thoth AI",
    icon: MessageSquare,
    tier: "elite",
    description: "AI assistant",
  },
  {
    href: "/settings",
    matchPath: "/settings",
    label: "Settings",
    icon: Settings,
    description: "Preferences",
  },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { user, isElite, logout, loading } = useAuth();

  const handleLogout = async () => {
    await logout();
    router.push("/");
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile Header */}
      <header className="lg:hidden fixed top-0 left-0 right-0 z-50 bg-card/95 backdrop-blur-xl border-b border-border h-14 flex items-center px-4">
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="mr-3"
        >
          {sidebarOpen ? (
            <X className="h-5 w-5" />
          ) : (
            <Menu className="h-5 w-5" />
          )}
        </Button>
        <div className="flex items-center gap-2">
          <ThothLogo size="small" />
          <span className="font-bold text-lg">Thoth</span>
        </div>
        {user && isElite && (
          <Badge variant="elite" className="ml-auto text-2xs">
            <Shield className="h-2.5 w-2.5 mr-1" />
            Elite
          </Badge>
        )}
      </header>

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed top-0 left-0 z-40 h-screen w-72 bg-card/95 backdrop-blur-xl border-r border-border transition-transform duration-300 ease-out lg:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="h-16 flex items-center gap-3 px-6 border-b border-border">
            <ThothLogo />
            <div className="flex flex-col">
              <span className="font-bold text-lg leading-tight">Thoth</span>
              <span className="text-xs text-muted-foreground">
                Dynasty Analytics
              </span>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
            {navItems.map((item) => {
              const isActive = item.exactMatch
                ? pathname === item.matchPath
                : pathname === item.matchPath || pathname.startsWith(item.matchPath + "/");
              const Icon = item.icon;

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={cn(
                    "group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                    isActive
                      ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                      : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                  )}
                >
                  <Icon
                    className={cn(
                      "h-5 w-5 transition-transform group-hover:scale-110",
                      isActive && "drop-shadow-sm"
                    )}
                  />
                  <div className="flex-1 flex flex-col">
                    <span>{item.label}</span>
                    {!isActive && (
                      <span className="text-2xs text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
                        {item.description}
                      </span>
                    )}
                  </div>
                  {item.tier === "elite" && !isElite && (
                    <Badge variant="elite" className="text-2xs px-1.5 py-0">
                      <Sparkles className="h-2.5 w-2.5 mr-0.5" />
                      Elite
                    </Badge>
                  )}
                  {item.tier === "elite" && isElite && (
                    <Badge variant="success" className="text-2xs px-1.5 py-0">
                      Unlocked
                    </Badge>
                  )}
                  {isActive && <ChevronRight className="h-4 w-4 opacity-60" />}
                </Link>
              );
            })}
          </nav>

          {/* Upgrade Banner - Only show if not Elite */}
          {!isElite && (
            <div className="p-4 border-t border-border">
              <div className="rounded-xl bg-gradient-to-br from-amber-500/10 via-yellow-500/5 to-amber-500/10 border border-amber-500/20 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="h-4 w-4 text-amber-500" />
                  <span className="text-sm font-semibold text-amber-600">
                    Upgrade to Elite
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mb-3">
                  Unlock ML projections, Thoth AI, and more.
                </p>
                <Button
                  variant="premium"
                  size="sm"
                  className="w-full"
                  asChild
                >
                  <Link href="/pricing">View Plans</Link>
                </Button>
              </div>
            </div>
          )}

          {/* User Section */}
          <div className="p-4 border-t border-border">
            {loading ? (
              <div className="flex items-center justify-center py-2">
                <div className="h-5 w-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              </div>
            ) : user ? (
              <div className="flex items-center gap-3 p-2 rounded-lg bg-secondary/50">
                <div className="h-9 w-9 rounded-full bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
                  <Shield className="h-4 w-4 text-black" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{user.email}</p>
                  <div className="flex items-center gap-1.5">
                    <Badge
                      variant={user.tier === "elite" ? "elite" : user.tier === "pro" ? "pro" : "free"}
                      className="text-2xs px-1.5 py-0"
                    >
                      {user.tier === "elite" && <Sparkles className="h-2.5 w-2.5 mr-0.5" />}
                      {user.tier.charAt(0).toUpperCase() + user.tier.slice(1)}
                    </Badge>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={handleLogout}
                  title="Sign out"
                >
                  <LogOut className="h-4 w-4" />
                </Button>
              </div>
            ) : (
              <Button variant="outline" className="w-full" asChild>
                <Link href="/login">
                  <LogIn className="h-4 w-4 mr-2" />
                  Sign In
                </Link>
              </Button>
            )}
          </div>
        </div>
      </aside>

      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main Content */}
      <main className="lg:pl-72 pt-14 lg:pt-0 min-h-screen">
        <div className="p-6 lg:p-8 max-w-7xl mx-auto">{children}</div>
      </main>
    </div>
  );
}
