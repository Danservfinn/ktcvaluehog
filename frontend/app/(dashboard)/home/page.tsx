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
import { Input } from "@/components/ui/input";
import {
  TrendingUp,
  TrendingDown,
  ArrowRight,
  Zap,
  Trophy,
  Sparkles,
  ArrowUpRight,
  ArrowDownRight,
  Loader2,
  AlertTriangle,
  Heart,
  Target,
  Users,
  ArrowLeftRight,
  LineChart,
  MessageSquare,
  Crown,
  Shield,
  Activity,
  Clock,
} from "lucide-react";
import Link from "next/link";
import { api, PlayerSummary } from "@/lib/api";
import { useAuth } from "@/contexts/auth-context";
import { AboutThoth } from "@/components/dashboard/about-thoth";

// Types
interface DashboardPlayer {
  name: string;
  pos: string;
  team: string;
  change: number;
  value: number;
}

interface LeagueInfo {
  league_id: string;
  name: string;
  record?: string;
  power_rank?: number;
  classification?: string;
  total_rosters?: number;
}

interface RosterAlert {
  type: "injury" | "value_spike" | "value_drop" | "age_cliff";
  player_name: string;
  position: string;
  message: string;
  severity: "high" | "medium" | "low";
}

interface TradeSuggestion {
  give: string[];
  get: string[];
  differential: number;
  rationale: string;
}

// Stat Card Component
function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  color,
  loading,
  locked,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ElementType;
  color: "emerald" | "amber" | "sky" | "purple" | "rose";
  loading?: boolean;
  locked?: boolean;
}) {
  const colorClasses = {
    emerald: "bg-emerald-500/15 text-emerald-600",
    amber: "bg-amber-500/15 text-amber-500",
    sky: "bg-sky-500/15 text-sky-600",
    purple: "bg-purple-500/15 text-purple-600",
    rose: "bg-rose-500/15 text-rose-600",
  };

  return (
    <Card variant="glass" className="p-4">
      <div className="flex items-center gap-3">
        <div
          className={`h-10 w-10 rounded-lg flex items-center justify-center ${colorClasses[color]}`}
        >
          <Icon className="h-5 w-5" />
        </div>
        <div className="flex-1 min-w-0">
          {loading ? (
            <div className="h-7 w-16 bg-secondary animate-pulse rounded" />
          ) : locked ? (
            <div className="flex items-center gap-1.5">
              <Sparkles className="h-4 w-4 text-amber-500" />
              <span className="text-sm text-muted-foreground">Elite</span>
            </div>
          ) : (
            <p className="text-2xl font-bold truncate">{value}</p>
          )}
          <p className="text-xs text-muted-foreground truncate">{title}</p>
          {subtitle && (
            <p className="text-2xs text-muted-foreground">{subtitle}</p>
          )}
        </div>
      </div>
    </Card>
  );
}

// Player Row Component
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
    <div className="flex items-center justify-between py-2.5 group">
      <div className="flex items-center gap-2.5 min-w-0">
        <Badge
          variant={pos.toLowerCase() as "qb" | "rb" | "wr" | "te"}
          className="w-9 justify-center text-xs"
        >
          {pos}
        </Badge>
        <div className="min-w-0">
          <p className="font-medium text-sm truncate">{name}</p>
          <p className="text-2xs text-muted-foreground">{team}</p>
        </div>
      </div>
      <div
        className={`flex items-center gap-1 font-mono text-sm ${
          isPositive ? "text-emerald-600" : "text-rose-600"
        }`}
      >
        {isPositive ? (
          <ArrowUpRight className="h-3.5 w-3.5" />
        ) : (
          <ArrowDownRight className="h-3.5 w-3.5" />
        )}
        <span>
          {isPositive ? "+" : ""}
          {change}
        </span>
      </div>
    </div>
  );
}

// Alert Row Component
function AlertRow({ alert }: { alert: RosterAlert }) {
  const iconMap = {
    injury: AlertTriangle,
    value_spike: TrendingUp,
    value_drop: TrendingDown,
    age_cliff: Clock,
  };
  const colorMap = {
    high: "text-rose-500 bg-rose-500/10",
    medium: "text-amber-500 bg-amber-500/10",
    low: "text-sky-500 bg-sky-500/10",
  };
  const Icon = iconMap[alert.type];

  return (
    <div className="flex items-start gap-3 py-2.5">
      <div className={`h-7 w-7 rounded-lg flex items-center justify-center ${colorMap[alert.severity]}`}>
        <Icon className="h-3.5 w-3.5" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-sm">{alert.player_name}</span>
          <Badge variant={alert.position.toLowerCase() as "qb" | "rb" | "wr" | "te"} className="text-2xs px-1.5 py-0">
            {alert.position}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">{alert.message}</p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { user, isElite, loading: authLoading } = useAuth();

  // Data states
  const [topRisers, setTopRisers] = useState<DashboardPlayer[]>([]);
  const [topFallers, setTopFallers] = useState<DashboardPlayer[]>([]);
  const [leagues, setLeagues] = useState<LeagueInfo[]>([]);
  const [alerts, setAlerts] = useState<RosterAlert[]>([]);
  const [tradeSuggestions, setTradeSuggestions] = useState<TradeSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [connectUsername, setConnectUsername] = useState("");
  const [connecting, setConnecting] = useState(false);

  // Stats
  const [stats, setStats] = useState({
    totalValue: 0,
    dynastyHealth: 0,
    championshipOdds: 0,
    buySignals: 0,
  });

  // Load saved leagues from localStorage
  useEffect(() => {
    const savedLeagues = localStorage.getItem("thoth_leagues");
    if (savedLeagues) {
      try {
        const parsed = JSON.parse(savedLeagues);
        setLeagues(parsed);
      } catch (e) {
        console.error("Failed to parse saved leagues:", e);
      }
    }
  }, []);

  // Fetch dashboard data
  useEffect(() => {
    async function fetchDashboardData() {
      try {
        // Fetch risers
        const risersResponse = await api.getRisers(7, 5);
        if (risersResponse.data) {
          setTopRisers(
            risersResponse.data.map((p) => ({
              name: p.name,
              pos: p.position,
              team: p.team || "FA",
              change: p.trend_value || 0,
              value: p.ktc_value,
            }))
          );
        }

        // Fetch fallers
        const fallersResponse = await api.getFallers(7, 5);
        if (fallersResponse.data) {
          setTopFallers(
            fallersResponse.data.map((p) => ({
              name: p.name,
              pos: p.position,
              team: p.team || "FA",
              change: p.trend_value || 0,
              value: p.ktc_value,
            }))
          );
        }

        // Fetch edge signals count
        const edgeResponse = await api.getEdgeSignals({ limit: 100 });
        if (edgeResponse.data) {
          const buySignals = edgeResponse.data.filter(
            (p) => p.signal === "BUY" || p.signal === "STRONG_BUY"
          ).length;
          setStats((prev) => ({ ...prev, buySignals }));
        }

        // If we have a connected league, fetch league analysis
        const savedLeagues = localStorage.getItem("thoth_leagues");
        if (savedLeagues) {
          const parsedLeagues = JSON.parse(savedLeagues);
          if (parsedLeagues.length > 0) {
            const primaryLeague = parsedLeagues[0];
            try {
              const analysis = await api.analyzeLeague(primaryLeague.league_id);
              if (analysis) {
                // Extract stats from league analysis
                if (analysis.your_analysis) {
                  setStats((prev) => ({
                    ...prev,
                    totalValue: analysis.your_analysis.total_ktc_value || 0,
                    dynastyHealth: analysis.your_dynasty_health?.total_score || 0,
                    championshipOdds: Math.round((analysis.your_championship_odds?.championship_probability || 0) * 100),
                  }));

                  // Generate alerts from roster analysis
                  const newAlerts: RosterAlert[] = [];

                  // Check for players with sell candidate status
                  if (analysis.your_analysis.players) {
                    analysis.your_analysis.players.slice(0, 5).forEach((player) => {
                      if (player.is_sell_candidate) {
                        newAlerts.push({
                          type: "value_drop",
                          player_name: player.name,
                          position: player.position,
                          message: "Consider selling - value may decline",
                          severity: "medium",
                        });
                      } else if (player.is_breakout_candidate) {
                        newAlerts.push({
                          type: "value_spike",
                          player_name: player.name,
                          position: player.position,
                          message: "Breakout potential - hold or buy more",
                          severity: "low",
                        });
                      }
                    });
                  }

                  setAlerts(newAlerts.slice(0, 5));
                }

                // Extract trade suggestions
                if (analysis.top_trade_suggestions && analysis.top_trade_suggestions.length > 0) {
                  setTradeSuggestions(
                    analysis.top_trade_suggestions.slice(0, 3).map((s) => ({
                      give: s.give_players?.map((p) => p.name) || [],
                      get: s.get_players?.map((p) => p.name) || [],
                      differential: s.value_differential || 0,
                      rationale: s.rationale || "Good trade opportunity",
                    }))
                  );
                }
              }
            } catch (e) {
              console.error("Failed to fetch league analysis:", e);
            }
          }
        }
      } catch (error) {
        console.error("Failed to fetch dashboard data:", error);
      } finally {
        setLoading(false);
      }
    }

    fetchDashboardData();
  }, []);

  // Connect Sleeper account
  const handleConnect = async () => {
    if (!connectUsername.trim()) return;
    setConnecting(true);
    try {
      const response = await api.connectSleeper(connectUsername.trim());
      if (response && response.leagues) {
        const leagueData = response.leagues.map((l) => ({
          league_id: l.league_id,
          name: l.name,
          total_rosters: l.total_rosters,
        }));
        setLeagues(leagueData);
        localStorage.setItem("thoth_leagues", JSON.stringify(leagueData));
        setConnectUsername("");
        // Refresh the page to load league data
        window.location.reload();
      }
    } catch (error) {
      console.error("Failed to connect Sleeper:", error);
    } finally {
      setConnecting(false);
    }
  };

  const hasLeagues = leagues.length > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          {user ? `Welcome back` : "Dashboard"}
        </h1>
        <p className="text-muted-foreground mt-1">
          {hasLeagues
            ? "Your dynasty command center"
            : "Connect your Sleeper league for personalized insights"}
        </p>
      </div>

      {/* Stats Row */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Roster Value"
          value={hasLeagues && stats.totalValue > 0 ? stats.totalValue.toLocaleString() : "--"}
          icon={Trophy}
          color="amber"
          loading={loading && hasLeagues}
        />
        <StatCard
          title="Dynasty Health"
          value={hasLeagues && stats.dynastyHealth > 0 ? `${stats.dynastyHealth}/100` : "--"}
          icon={Heart}
          color="emerald"
          loading={loading && hasLeagues}
          locked={!isElite && hasLeagues}
        />
        <StatCard
          title="Championship Odds"
          value={hasLeagues && stats.championshipOdds > 0 ? `${stats.championshipOdds}%` : "--"}
          icon={Crown}
          color="purple"
          loading={loading && hasLeagues}
          locked={!isElite && hasLeagues}
        />
        <StatCard
          title="Buy Signals"
          value={stats.buySignals}
          subtitle="Undervalued players"
          icon={Target}
          color="sky"
          loading={loading}
        />
      </div>

      {/* Main Grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* My Leagues */}
        <Card variant="glass" className="lg:col-span-1">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-amber-500/15 flex items-center justify-center">
                  <Trophy className="h-4 w-4 text-amber-500" />
                </div>
                My Leagues
              </CardTitle>
              {hasLeagues && (
                <Badge variant="secondary" className="text-xs">
                  {leagues.length}
                </Badge>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {hasLeagues ? (
              <div className="space-y-2">
                {leagues.slice(0, 3).map((league) => (
                  <Link
                    key={league.league_id}
                    href={`/league?id=${league.league_id}`}
                    className="block p-3 rounded-lg bg-secondary/30 hover:bg-secondary/50 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-sm">{league.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {league.total_rosters} teams
                        </p>
                      </div>
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                    </div>
                  </Link>
                ))}
                <Button variant="outline" size="sm" className="w-full mt-2" asChild>
                  <Link href="/league">View All Leagues</Link>
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  Connect your Sleeper account to unlock personalized insights, trade suggestions, and championship odds.
                </p>
                <div className="flex gap-2">
                  <Input
                    placeholder="Sleeper username"
                    value={connectUsername}
                    onChange={(e) => setConnectUsername(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleConnect()}
                    className="flex-1"
                  />
                  <Button
                    onClick={handleConnect}
                    disabled={connecting || !connectUsername.trim()}
                  >
                    {connecting ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      "Connect"
                    )}
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Roster Alerts / Trade Opportunities */}
        <Card variant="glass" className="lg:col-span-2">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-rose-500/15 flex items-center justify-center">
                  <AlertTriangle className="h-4 w-4 text-rose-500" />
                </div>
                {hasLeagues ? "Roster Alerts" : "Trade Opportunities"}
              </CardTitle>
            </div>
            <CardDescription>
              {hasLeagues
                ? "Important updates about your players"
                : "Top buy and sell signals from our models"}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : hasLeagues && alerts.length > 0 ? (
              <div className="divide-y divide-border/50">
                {alerts.map((alert, i) => (
                  <AlertRow key={i} alert={alert} />
                ))}
              </div>
            ) : hasLeagues ? (
              <div className="text-center py-6">
                <Shield className="h-8 w-8 text-emerald-500 mx-auto mb-2" />
                <p className="text-sm text-muted-foreground">
                  No urgent alerts for your roster
                </p>
              </div>
            ) : (
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <h4 className="text-sm font-medium text-emerald-600 mb-2 flex items-center gap-1.5">
                    <TrendingUp className="h-4 w-4" /> Buy Targets
                  </h4>
                  <div className="space-y-1">
                    {topRisers.slice(0, 3).map((player) => (
                      <div
                        key={player.name}
                        className="flex items-center justify-between p-2 rounded-lg bg-emerald-500/5"
                      >
                        <div className="flex items-center gap-2">
                          <Badge
                            variant={player.pos.toLowerCase() as any}
                            className="text-2xs px-1.5"
                          >
                            {player.pos}
                          </Badge>
                          <span className="text-sm font-medium">{player.name}</span>
                        </div>
                        <span className="text-xs text-emerald-600">+{player.change}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <h4 className="text-sm font-medium text-rose-600 mb-2 flex items-center gap-1.5">
                    <TrendingDown className="h-4 w-4" /> Sell Candidates
                  </h4>
                  <div className="space-y-1">
                    {topFallers.slice(0, 3).map((player) => (
                      <div
                        key={player.name}
                        className="flex items-center justify-between p-2 rounded-lg bg-rose-500/5"
                      >
                        <div className="flex items-center gap-2">
                          <Badge
                            variant={player.pos.toLowerCase() as any}
                            className="text-2xs px-1.5"
                          >
                            {player.pos}
                          </Badge>
                          <span className="text-sm font-medium">{player.name}</span>
                        </div>
                        <span className="text-xs text-rose-600">{player.change}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Market Movers */}
        <Card variant="glass" className="lg:col-span-2">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-sky-500/15 flex items-center justify-center">
                  <Activity className="h-4 w-4 text-sky-600" />
                </div>
                Market Movers
              </CardTitle>
              <Badge variant="secondary" className="text-xs">7D</Badge>
            </div>
            <CardDescription>Biggest value changes this week</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : (
              <div className="grid md:grid-cols-2 gap-6">
                {/* Risers */}
                <div>
                  <h4 className="text-sm font-medium text-emerald-600 mb-3 flex items-center gap-1.5">
                    <TrendingUp className="h-4 w-4" /> Top Risers
                  </h4>
                  <div className="divide-y divide-border/50">
                    {topRisers.map((player) => (
                      <PlayerRow key={player.name} {...player} />
                    ))}
                  </div>
                </div>
                {/* Fallers */}
                <div>
                  <h4 className="text-sm font-medium text-rose-600 mb-3 flex items-center gap-1.5">
                    <TrendingDown className="h-4 w-4" /> Top Fallers
                  </h4>
                  <div className="divide-y divide-border/50">
                    {topFallers.map((player) => (
                      <PlayerRow key={player.name} {...player} />
                    ))}
                  </div>
                </div>
              </div>
            )}
            <Link
              href="/rankings"
              className="text-sm text-primary hover:text-primary/80 flex items-center gap-1.5 pt-4 font-medium transition-colors"
            >
              View all rankings <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card variant="glass" className="lg:col-span-1">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-purple-500/15 flex items-center justify-center">
                <Zap className="h-4 w-4 text-purple-600" />
              </div>
              Quick Actions
            </CardTitle>
            <CardDescription>Common tasks</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button variant="outline" className="w-full justify-start" asChild>
              <Link href="/trade">
                <ArrowLeftRight className="h-4 w-4 mr-2" />
                Analyze a Trade
              </Link>
            </Button>
            <Button variant="outline" className="w-full justify-start" asChild>
              <Link href="/rankings">
                <Users className="h-4 w-4 mr-2" />
                Search Players
              </Link>
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start"
              asChild
              disabled={!isElite}
            >
              <Link href="/projections">
                <LineChart className="h-4 w-4 mr-2" />
                ML Projections
                {!isElite && (
                  <Badge variant="elite" className="ml-auto text-2xs">
                    Elite
                  </Badge>
                )}
              </Link>
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start"
              asChild
              disabled={!isElite}
            >
              <Link href="/chat">
                <MessageSquare className="h-4 w-4 mr-2" />
                Ask Thoth AI
                {!isElite && (
                  <Badge variant="elite" className="ml-auto text-2xs">
                    Elite
                  </Badge>
                )}
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Trade Suggestions (if league connected and Elite) */}
      {hasLeagues && isElite && tradeSuggestions.length > 0 && (
        <Card variant="premium" className="glow-gold">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-amber-500/20 flex items-center justify-center">
                  <Sparkles className="h-4 w-4 text-amber-500" />
                </div>
                Suggested Trades
              </CardTitle>
              <Badge variant="elite" className="text-xs">
                <Sparkles className="h-3 w-3 mr-1" />
                Elite
              </Badge>
            </div>
            <CardDescription>AI-powered trade recommendations for your roster</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-3 gap-4">
              {tradeSuggestions.map((trade, i) => (
                <div
                  key={i}
                  className="p-4 rounded-lg bg-background/50 border border-border/50"
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs text-muted-foreground">Trade #{i + 1}</span>
                    <Badge
                      variant={trade.differential > 0 ? "success" : "secondary"}
                      className="text-2xs"
                    >
                      {trade.differential > 0 ? "+" : ""}
                      {trade.differential} value
                    </Badge>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div>
                      <span className="text-rose-500 font-medium">Give:</span>{" "}
                      {trade.give.join(", ")}
                    </div>
                    <div>
                      <span className="text-emerald-500 font-medium">Get:</span>{" "}
                      {trade.get.join(", ")}
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground mt-3">{trade.rationale}</p>
                </div>
              ))}
            </div>
            <Link
              href="/league"
              className="text-sm text-primary hover:text-primary/80 flex items-center gap-1.5 pt-4 font-medium transition-colors"
            >
              View all trade suggestions <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </CardContent>
        </Card>
      )}

      {/* About Thoth Section */}
      <section id="about" className="mt-8 pt-8 border-t border-border/50 scroll-mt-20">
        <AboutThoth />
      </section>
    </div>
  );
}
