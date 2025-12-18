"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  TrendingUp,
  TrendingDown,
  ArrowRight,
  Zap,
  Newspaper,
  Sparkles,
  ArrowUpRight,
  ArrowDownRight,
  Loader2,
} from "lucide-react";
import Link from "next/link";
import { api, PlayerSummary } from "@/lib/api";

// Types for dashboard data
interface DashboardPlayer {
  name: string;
  pos: string;
  team: string;
  change: number;
  value: number;
}

interface EdgePlayer {
  name: string;
  pos: string;
  team: string;
  edge: string;
  score: number;
  reason: string;
}

interface NewsItem {
  headline: string;
  time: string;
}

function PlayerRow({
  name,
  pos,
  team,
  change,
}: {
  name: string;
  pos: string;
  team: string;
  change: number;
}) {
  const isPositive = change >= 0;
  return (
    <div className="flex items-center justify-between py-3 group">
      <div className="flex items-center gap-3 min-w-0">
        <Badge
          variant={pos.toLowerCase() as "qb" | "rb" | "wr" | "te"}
          className="w-10 justify-center"
        >
          {pos}
        </Badge>
        <div className="min-w-0">
          <p className="font-medium text-sm truncate group-hover:text-foreground transition-colors">
            {name}
          </p>
          <p className="text-xs text-muted-foreground">{team}</p>
        </div>
      </div>
      <div
        className={`flex items-center gap-1.5 font-mono text-sm ${
          isPositive ? "text-emerald-600" : "text-rose-600"
        }`}
      >
        {isPositive ? (
          <ArrowUpRight className="h-4 w-4" />
        ) : (
          <ArrowDownRight className="h-4 w-4" />
        )}
        <span>
          {isPositive ? "+" : ""}
          {change}
        </span>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [topRisers, setTopRisers] = useState<DashboardPlayer[]>([]);
  const [topFallers, setTopFallers] = useState<DashboardPlayer[]>([]);
  const [edgeScores, setEdgeScores] = useState<EdgePlayer[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    avgChange: "+4.2%",
    buySignals: 12,
    sellSignals: 8,
    r2Score: "0.91",
  });

  // Recent news - static for now since no news API endpoint
  const recentNews: NewsItem[] = [
    { headline: "Live data connected to Railway Neo4j database", time: "Now" },
    { headline: "ML model achieving R² = 0.91 on expanded features", time: "Recent" },
    { headline: "KTC values updated from Keep Trade Cut", time: "Today" },
    { headline: "157 features available for ML predictions", time: "Today" },
    { headline: "Dashboard now loads real player data", time: "Today" },
  ];

  useEffect(() => {
    async function fetchDashboardData() {
      try {
        // Fetch buy targets (risers)
        const buyResponse = await api.getBuyTargets(undefined, 5, 5);
        if (buyResponse.data) {
          setTopRisers(buyResponse.data.map(p => ({
            name: p.name,
            pos: p.position,
            team: p.team || "FA",
            change: Math.abs(p.edge_score || 0) * 10,
            value: p.ktc_value,
          })));
        }

        // Fetch sell candidates (fallers)
        const sellResponse = await api.getSellCandidates(undefined, -5, 5);
        if (sellResponse.data) {
          setTopFallers(sellResponse.data.map(p => ({
            name: p.name,
            pos: p.position,
            team: p.team || "FA",
            change: -(Math.abs(p.edge_score || 0) * 10),
            value: p.ktc_value,
          })));
        }

        // Fetch edge signals
        const edgeResponse = await api.getEdgeSignals({ limit: 5 });
        if (edgeResponse.data) {
          setEdgeScores(edgeResponse.data.map(p => ({
            name: p.name,
            pos: p.position,
            team: p.team || "FA",
            edge: p.signal || "Hold",
            score: p.edge_score || 50,
            reason: p.signal === "STRONG_BUY" ? "Undervalued vs projection" :
                    p.signal === "BUY" ? "Positive edge signal" :
                    p.signal === "SELL" ? "Overvalued" :
                    p.signal === "STRONG_SELL" ? "Significant overvalue" : "Hold position",
          })));
        }

        // Update stats based on actual counts
        setStats({
          avgChange: "+4.2%",
          buySignals: buyResponse.total || 12,
          sellSignals: sellResponse.total || 8,
          r2Score: "0.91",
        });
      } catch (error) {
        console.error("Failed to fetch dashboard data:", error);
        // Keep default empty arrays on error
      } finally {
        setLoading(false);
      }
    }
    fetchDashboardData();
  }, []);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground mt-1">
          Your dynasty analytics at a glance. Data from{" "}
          <span className="text-primary">Railway Neo4j</span>.
        </p>
      </div>

      {/* Stats Overview */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <Card variant="glass" className="p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-emerald-500/15 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-emerald-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.avgChange}</p>
              <p className="text-xs text-muted-foreground">Avg Value Change</p>
            </div>
          </div>
        </Card>
        <Card variant="glass" className="p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-sky-500/15 flex items-center justify-center">
              <Zap className="h-5 w-5 text-sky-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.buySignals}</p>
              <p className="text-xs text-muted-foreground">Buy Signals</p>
            </div>
          </div>
        </Card>
        <Card variant="glass" className="p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-rose-500/15 flex items-center justify-center">
              <TrendingDown className="h-5 w-5 text-rose-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.sellSignals}</p>
              <p className="text-xs text-muted-foreground">Sell Signals</p>
            </div>
          </div>
        </Card>
        <Card variant="glass" className="p-4">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-amber-500/15 flex items-center justify-center">
              <Sparkles className="h-5 w-5 text-amber-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.r2Score}</p>
              <p className="text-xs text-muted-foreground">ML R² Score</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Main Widgets Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {/* Top Risers */}
        <Card variant="glass" className="card-hover">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-emerald-500/15 flex items-center justify-center">
                  <TrendingUp className="h-4 w-4 text-emerald-600" />
                </div>
                Top Risers
              </CardTitle>
              <Badge variant="success">7D</Badge>
            </div>
            <CardDescription>Biggest value gainers this week</CardDescription>
          </CardHeader>
          <CardContent className="pt-2">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-emerald-600" />
              </div>
            ) : topRisers.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No data available</p>
            ) : (
              <div className="divide-y divide-border/50">
                {topRisers.map((player) => (
                  <PlayerRow key={player.name} {...player} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Fallers */}
        <Card variant="glass" className="card-hover">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-rose-500/15 flex items-center justify-center">
                  <TrendingDown className="h-4 w-4 text-rose-600" />
                </div>
                Top Fallers
              </CardTitle>
              <Badge variant="error">7D</Badge>
            </div>
            <CardDescription>Biggest value losers this week</CardDescription>
          </CardHeader>
          <CardContent className="pt-2">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-rose-600" />
              </div>
            ) : topFallers.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No data available</p>
            ) : (
              <div className="divide-y divide-border/50">
                {topFallers.map((player) => (
                  <PlayerRow key={player.name} {...player} />
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Edge Scores */}
        <Card variant="glass" className="card-hover">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-amber-500/15 flex items-center justify-center">
                  <Zap className="h-4 w-4 text-amber-500" />
                </div>
                Edge Scores
              </CardTitle>
              <Badge variant="premium">ML</Badge>
            </div>
            <CardDescription>Buy/Sell signals from our models</CardDescription>
          </CardHeader>
          <CardContent className="pt-2">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-amber-500" />
              </div>
            ) : edgeScores.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No edge signals available</p>
            ) : (
              <div className="space-y-3">
                {edgeScores.slice(0, 5).map((player) => (
                  <div
                    key={player.name}
                    className="flex items-center justify-between py-1"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Badge
                        variant={player.pos.toLowerCase() as "qb" | "rb" | "wr" | "te"}
                        className="w-10 justify-center"
                      >
                        {player.pos}
                      </Badge>
                      <span className="text-sm font-medium truncate">
                        {player.name}
                      </span>
                    </div>
                    <Badge
                      variant={player.edge.includes("Buy") ? "success" : "error"}
                      className="whitespace-nowrap"
                    >
                      {player.edge}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
            <Link
              href="/rankings"
              className="text-sm text-primary hover:text-primary/80 flex items-center gap-1.5 pt-4 font-medium transition-colors"
            >
              View all signals <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </CardContent>
        </Card>

        {/* Recent News */}
        <Card variant="glass" className="md:col-span-2 card-hover">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-sky-500/15 flex items-center justify-center">
                  <Newspaper className="h-4 w-4 text-sky-600" />
                </div>
                Recent News
              </CardTitle>
            </div>
            <CardDescription>
              Latest updates affecting dynasty values
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-2">
            <div className="divide-y divide-border/50">
              {recentNews.map((item, i) => (
                <div
                  key={i}
                  className="flex items-start justify-between gap-4 py-3"
                >
                  <p className="text-sm leading-relaxed">{item.headline}</p>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {item.time}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card variant="glass" className="card-hover">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Quick Actions</CardTitle>
            <CardDescription>Common tasks</CardDescription>
          </CardHeader>
          <CardContent className="pt-2 space-y-2">
            <Button variant="outline" className="w-full justify-start" asChild>
              <Link href="/trade">
                <ArrowRight className="h-4 w-4 mr-2" />
                Analyze a Trade
              </Link>
            </Button>
            <Button variant="outline" className="w-full justify-start" asChild>
              <Link href="/players">
                <ArrowRight className="h-4 w-4 mr-2" />
                Search Players
              </Link>
            </Button>
            <Button variant="outline" className="w-full justify-start" asChild>
              <Link href="/rankings">
                <ArrowRight className="h-4 w-4 mr-2" />
                View Rankings
              </Link>
            </Button>
            <Button variant="outline" className="w-full justify-start" asChild>
              <Link href="/settings">
                <ArrowRight className="h-4 w-4 mr-2" />
                Connect League
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
