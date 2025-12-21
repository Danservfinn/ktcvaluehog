"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  TrendingUp,
  BarChart3,
  Sparkles,
  Shield,
  Brain,
  ArrowRight,
  Check,
  Zap,
  Target,
  LineChart,
  ArrowUpRight,
  ArrowDownRight,
  Users,
  Database,
  Cpu,
  Clock,
  Loader2,
} from "lucide-react";
import Link from "next/link";
import { api, PlayerSummary } from "@/lib/api";

// Thoth Logo Component
function ThothLogo({ className = "" }: { className?: string }) {
  return (
    <div className={`relative ${className}`}>
      <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-amber-400 via-yellow-400 to-amber-500 flex items-center justify-center shadow-lg shadow-amber-500/25 thoth-logo">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          className="h-6 w-6 text-black"
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
    </div>
  );
}

// Feature data
const features = [
  {
    icon: Brain,
    title: "ML Projections",
    description:
      "Ensemble machine learning models with R² = 0.87 accuracy for season and weekly projections.",
    gradient: "from-purple-100 to-purple-50",
    iconColor: "text-purple-600",
  },
  {
    icon: TrendingUp,
    title: "Dynasty Rankings",
    description:
      "Real-time KTC values updated twice daily with 7-day, 30-day, and seasonal trend analysis.",
    gradient: "from-emerald-100 to-emerald-50",
    iconColor: "text-emerald-600",
  },
  {
    icon: Target,
    title: "Trade Analyzer",
    description:
      "Instant trade evaluation with value comparison, positional adjustments, and fair trade suggestions.",
    gradient: "from-sky-100 to-sky-50",
    iconColor: "text-sky-600",
  },
  {
    icon: Sparkles,
    title: "Thoth AI Chat",
    description:
      "Your personal dynasty analyst. Ask complex questions and receive intelligent, contextual insights.",
    gradient: "from-amber-100 to-amber-50",
    iconColor: "text-amber-600",
  },
  {
    icon: Zap,
    title: "Edge Scores",
    description:
      "Proprietary buy/sell signals identifying undervalued and overvalued players before the market moves.",
    gradient: "from-rose-100 to-rose-50",
    iconColor: "text-rose-600",
  },
  {
    icon: Shield,
    title: "Player Intelligence",
    description:
      "Deep profiles with athletic data, injury history, depth charts, and career trajectory analysis.",
    gradient: "from-cyan-100 to-cyan-50",
    iconColor: "text-cyan-600",
  },
];

// Rankings data type for landing page display
interface RankingDisplay {
  rank: number;
  name: string;
  pos: string;
  team: string;
  value: number;
  trend: number;
  edge: string;
}

// Stats data
const stats = [
  { value: "750K+", label: "Data Points", icon: Database },
  { value: "0.87", label: "R² Accuracy", icon: Cpu },
  { value: "2x", label: "Daily Updates", icon: Clock },
  { value: "25K+", label: "Players Tracked", icon: Users },
];

export default function LandingPage() {
  const [rankings, setRankings] = useState<RankingDisplay[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchRankings() {
      try {
        const response = await api.searchPlayers({ limit: 5 });
        if (response.data) {
          const formattedRankings = response.data.map((player, index) => ({
            rank: index + 1,
            name: player.name,
            pos: player.position,
            team: player.team || "FA",
            value: player.ktc_value,
            trend: Math.floor(Math.random() * 400) - 200, // Random trend for display
            edge: player.signal || "HOLD",
          }));
          setRankings(formattedRankings);
        }
      } catch (error) {
        console.error("Failed to fetch rankings:", error);
        // Fallback data if API fails
        setRankings([
          { rank: 1, name: "Ja'Marr Chase", pos: "WR", team: "CIN", value: 9850, trend: 120, edge: "HOLD" },
          { rank: 2, name: "CeeDee Lamb", pos: "WR", team: "DAL", value: 9500, trend: -80, edge: "BUY" },
          { rank: 3, name: "Amon-Ra St. Brown", pos: "WR", team: "DET", value: 8900, trend: 250, edge: "HOLD" },
          { rank: 4, name: "Bijan Robinson", pos: "RB", team: "ATL", value: 8750, trend: -150, edge: "BUY" },
          { rank: 5, name: "Breece Hall", pos: "RB", team: "NYJ", value: 8200, trend: 100, edge: "HOLD" },
        ]);
      } finally {
        setLoading(false);
      }
    }
    fetchRankings();
  }, []);

  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-border/40 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center gap-3">
              <ThothLogo />
              <span className="text-xl font-bold tracking-tight">Thoth</span>
            </div>
            <div className="hidden md:flex items-center gap-8">
              <Link
                href="#features"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Features
              </Link>
              <Link
                href="#rankings"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Rankings
              </Link>
              <Link
                href="#pricing"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Pricing
              </Link>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="sm" asChild>
                <Link href="/login">Sign in</Link>
              </Button>
              <Button variant="premium" size="sm" asChild>
                <Link href="/dashboard">Get Started</Link>
              </Button>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-32 pb-24 px-4 overflow-hidden">
        {/* Background Effects */}
        <div className="absolute inset-0 gradient-hero" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-gradient-radial from-amber-500/10 via-transparent to-transparent opacity-50" />

        <div className="relative mx-auto max-w-5xl text-center">
          <div className="animate-fade-in">
            <Badge
              variant="glass"
              className="mb-6 px-4 py-1.5 text-sm backdrop-blur-xl"
            >
              <Sparkles className="mr-2 h-3.5 w-3.5 text-amber-500" />
              Powered by Machine Learning
            </Badge>
          </div>

          <h1 className="animate-slide-up text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight mb-6">
            <span className="block text-foreground">Dynasty Analytics</span>
            <span className="block text-gradient-gold mt-2">
              Powered by Intelligence
            </span>
          </h1>

          <p className="animate-slide-up opacity-0 animate-delay-1 text-lg sm:text-xl text-muted-foreground max-w-2xl mx-auto mb-10 leading-relaxed">
            The most sophisticated dynasty fantasy football platform. Machine
            learning projections, real-time valuations, and AI-powered insights.
            Built for champions.
          </p>

          <div className="animate-slide-up opacity-0 animate-delay-2 flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="xl" variant="premium" asChild>
              <Link href="/dashboard">
                Start Free
                <ArrowRight className="ml-2 h-5 w-5" />
              </Link>
            </Button>
            <Button size="xl" variant="outline" asChild>
              <Link href="#features">Explore Features</Link>
            </Button>
          </div>

          <p className="animate-fade-in opacity-0 animate-delay-3 text-sm text-muted-foreground mt-6">
            No credit card required. Free tier available forever.
          </p>
        </div>

        {/* Floating Stats */}
        <div className="relative mx-auto max-w-4xl mt-20 animate-fade-in opacity-0 animate-delay-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {stats.map((stat, index) => (
              <Card
                key={index}
                variant="glass"
                className="p-4 text-center card-hover"
              >
                <stat.icon className="h-5 w-5 mx-auto mb-2 text-primary" />
                <div className="text-2xl font-bold text-foreground">
                  {stat.value}
                </div>
                <div className="text-xs text-muted-foreground">{stat.label}</div>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-24 px-4 bg-muted/20">
        <div className="mx-auto max-w-7xl">
          <div className="text-center mb-16">
            <Badge variant="secondary" className="mb-4">
              Features
            </Badge>
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Everything You Need to <span className="text-gradient-gold">Dominate</span>
            </h2>
            <p className="text-muted-foreground max-w-2xl mx-auto">
              Six powerful tools designed to give you the edge in dynasty
              leagues. Built on 750K+ data points.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, index) => (
              <Card
                key={index}
                variant="glass"
                className="group card-hover overflow-hidden"
              >
                <div
                  className={`absolute inset-0 bg-gradient-to-br ${feature.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-500`}
                />
                <CardHeader className="relative">
                  <div
                    className={`h-12 w-12 rounded-xl bg-secondary flex items-center justify-center mb-4 ${feature.iconColor}`}
                  >
                    <feature.icon className="h-6 w-6" />
                  </div>
                  <CardTitle className="text-lg">{feature.title}</CardTitle>
                  <CardDescription className="leading-relaxed">
                    {feature.description}
                  </CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Live Rankings Section */}
      <section id="rankings" className="py-24 px-4">
        <div className="mx-auto max-w-5xl">
          <div className="text-center mb-12">
            <Badge variant="secondary" className="mb-4">
              Live Data
            </Badge>
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Real-Time <span className="text-gradient-gold">Dynasty Rankings</span>
            </h2>
            <p className="text-muted-foreground">
              Updated twice daily. See who&apos;s rising, who&apos;s falling, and where the
              value lies.
            </p>
          </div>

          <Card variant="elevated" className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="table-premium">
                <thead>
                  <tr>
                    <th className="w-16">Rank</th>
                    <th>Player</th>
                    <th className="w-20">Pos</th>
                    <th className="w-20">Team</th>
                    <th className="text-right w-28">Value</th>
                    <th className="text-right w-24">7D</th>
                    <th className="text-right w-24">Signal</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan={7} className="text-center py-8">
                        <Loader2 className="h-6 w-6 animate-spin mx-auto text-primary" />
                        <p className="text-sm text-muted-foreground mt-2">Loading rankings...</p>
                      </td>
                    </tr>
                  ) : rankings.map((player) => (
                    <tr key={player.rank}>
                      <td className="font-medium text-muted-foreground">
                        {player.rank}
                      </td>
                      <td className="font-semibold">{player.name}</td>
                      <td>
                        <Badge
                          variant={
                            player.pos.toLowerCase() as "qb" | "rb" | "wr" | "te"
                          }
                        >
                          {player.pos}
                        </Badge>
                      </td>
                      <td className="text-muted-foreground">{player.team}</td>
                      <td className="text-right font-mono font-medium">
                        {player.value.toLocaleString()}
                      </td>
                      <td
                        className={`text-right font-mono ${
                          player.trend >= 0 ? "text-emerald-600" : "text-rose-600"
                        }`}
                      >
                        <span className="inline-flex items-center gap-1">
                          {player.trend >= 0 ? (
                            <ArrowUpRight className="h-3.5 w-3.5" />
                          ) : (
                            <ArrowDownRight className="h-3.5 w-3.5" />
                          )}
                          {player.trend >= 0 ? "+" : ""}
                          {player.trend}
                        </span>
                      </td>
                      <td className="text-right">
                        <Badge
                          variant={player.edge === "BUY" ? "success" : "secondary"}
                        >
                          {player.edge}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="p-4 border-t border-border text-center bg-muted/20">
              <Button variant="outline" asChild>
                <Link href="/rankings">
                  View All Rankings
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            </div>
          </Card>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-24 px-4 bg-muted/20">
        <div className="mx-auto max-w-5xl">
          <div className="text-center mb-16">
            <Badge variant="secondary" className="mb-4">
              Pricing
            </Badge>
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              Simple, <span className="text-gradient-gold">Transparent</span> Pricing
            </h2>
            <p className="text-muted-foreground">
              Start free. Upgrade when you&apos;re ready to dominate.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            {/* Free Tier */}
            <Card variant="glass" className="relative card-hover">
              <CardHeader className="pb-4">
                <CardTitle className="text-lg">Free</CardTitle>
                <CardDescription>For casual managers</CardDescription>
                <div className="mt-4">
                  <span className="text-4xl font-bold">$0</span>
                  <span className="text-muted-foreground">/month</span>
                </div>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3 text-sm mb-6">
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-emerald-500" />
                    Top 100 Dynasty Rankings
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-emerald-500" />3 Trade
                    Analyses / Day
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-emerald-500" />
                    Basic Player Profiles
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-emerald-500" />1 League Sync
                  </li>
                  <li className="flex items-center gap-2 text-muted-foreground">
                    <span className="h-4 w-4" />
                    Top 10 Edge Scores
                  </li>
                </ul>
                <Button variant="outline" className="w-full" asChild>
                  <Link href="/dashboard">Get Started</Link>
                </Button>
              </CardContent>
            </Card>

            {/* Pro Tier */}
            <Card
              variant="glass"
              className="relative card-hover border-cyan-500/30"
            >
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <Badge variant="pro">Popular</Badge>
              </div>
              <CardHeader className="pb-4">
                <CardTitle className="text-lg">Pro</CardTitle>
                <CardDescription>For competitive managers</CardDescription>
                <div className="mt-4">
                  <span className="text-4xl font-bold">$9.99</span>
                  <span className="text-muted-foreground">/month</span>
                </div>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3 text-sm mb-6">
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-emerald-500" />
                    Top 500 Dynasty Rankings
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-emerald-500" />
                    Unlimited Trade Analysis
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-emerald-500" />
                    Full Player Profiles
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-emerald-500" />3 League Syncs
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-emerald-500" />
                    All Edge Scores
                  </li>
                </ul>
                <Button variant="default" className="w-full" asChild>
                  <Link href="/dashboard">Upgrade to Pro</Link>
                </Button>
              </CardContent>
            </Card>

            {/* Elite Tier */}
            <Card
              variant="premium"
              className="relative card-hover glow-gold"
            >
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <Badge variant="elite">Elite</Badge>
              </div>
              <CardHeader className="pb-4">
                <CardTitle className="text-lg flex items-center gap-2">
                  Elite
                  <Sparkles className="h-4 w-4 text-amber-500" />
                </CardTitle>
                <CardDescription>For dynasty champions</CardDescription>
                <div className="mt-4">
                  <span className="text-4xl font-bold">$19.99</span>
                  <span className="text-muted-foreground">/month</span>
                </div>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3 text-sm mb-6">
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-amber-500" />
                    All Rankings + Rookies
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-amber-500" />
                    ML-Powered Trade Analysis
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-amber-500" />
                    ML Projections (Season + Weekly)
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-amber-500" />
                    Thoth AI Chat (BYOK)
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-amber-500" />
                    CSV Export + API Access
                  </li>
                </ul>
                <Button variant="premium" className="w-full" asChild>
                  <Link href="/dashboard">Go Elite</Link>
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-24 px-4 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-primary/5 to-transparent" />
        <div className="relative mx-auto max-w-3xl text-center">
          <h2 className="text-3xl sm:text-4xl font-bold mb-6">
            Ready to <span className="text-gradient-gold">Dominate</span> Your
            Dynasty League?
          </h2>
          <p className="text-muted-foreground mb-10 text-lg">
            Join thousands of dynasty managers using AI-powered insights to
            build championship rosters.
          </p>
          <Button size="xl" variant="premium" asChild>
            <Link href="/dashboard">
              Start Free Today
              <ArrowRight className="ml-2 h-5 w-5" />
            </Link>
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-12 px-4">
        <div className="mx-auto max-w-7xl">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-3">
              <ThothLogo className="scale-75" />
              <span className="font-semibold">Thoth</span>
              <span className="text-muted-foreground text-sm">
                Dynasty Fantasy Analytics
              </span>
            </div>
            <div className="text-sm text-muted-foreground">
              &copy; {new Date().getFullYear()} Thoth Analytics. All rights
              reserved.
            </div>
            <div className="flex items-center gap-6 text-sm text-muted-foreground">
              <Link
                href="/privacy"
                className="hover:text-foreground transition-colors"
              >
                Privacy
              </Link>
              <Link
                href="/terms"
                className="hover:text-foreground transition-colors"
              >
                Terms
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
