"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAuth } from "@/contexts/auth-context";
import { api, SleeperLeague, LeagueAnalysis } from "@/lib/api";
import {
  Trophy,
  Users,
  TrendingUp,
  TrendingDown,
  ArrowLeftRight,
  Target,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  Minus,
  Loader2,
  AlertCircle,
  RefreshCw,
  ArrowLeft,
  Crown,
  Sparkles,
  Heart,
  Zap,
  Search,
  ArrowRight,
  Shield,
} from "lucide-react";
import { cn } from "@/lib/utils";

// Position color mapping
const positionColors: Record<string, string> = {
  QB: "bg-amber-500/10 text-amber-600 border-amber-500/30",
  RB: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30",
  WR: "bg-sky-500/10 text-sky-600 border-sky-500/30",
  TE: "bg-purple-500/10 text-purple-600 border-purple-500/30",
};

const classificationColors: Record<string, string> = {
  CONTENDER: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30",
  FRINGE: "bg-amber-500/10 text-amber-600 border-amber-500/30",
  REBUILDER: "bg-sky-500/10 text-sky-600 border-sky-500/30",
};

const gradeColors: Record<string, string> = {
  "A+": "text-emerald-600",
  A: "text-emerald-500",
  "B+": "text-green-500",
  B: "text-green-400",
  "C+": "text-amber-500",
  C: "text-amber-400",
  D: "text-orange-500",
  F: "text-red-500",
};

function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  variant = "default",
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ComponentType<{ className?: string }>;
  variant?: "default" | "success" | "warning" | "danger";
}) {
  const variantClasses = {
    default: "from-primary/10 to-primary/5",
    success: "from-emerald-500/10 to-emerald-500/5",
    warning: "from-amber-500/10 to-amber-500/5",
    danger: "from-red-500/10 to-red-500/5",
  };

  return (
    <Card variant="glass" className="overflow-hidden">
      <div className={cn("absolute inset-0 bg-gradient-to-br opacity-50", variantClasses[variant])} />
      <CardContent className="p-4 relative">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wide">{title}</p>
            <p className="text-2xl font-bold mt-1">{value}</p>
            {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
          </div>
          {Icon && (
            <div className="h-10 w-10 rounded-lg bg-background/50 flex items-center justify-center">
              <Icon className="h-5 w-5 text-primary" />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function HealthGauge({ score, size = "default" }: { score: number; size?: "default" | "small" }) {
  const dimensions = size === "small" ? "h-24 w-24" : "h-32 w-32";
  const strokeWidth = size === "small" ? 8 : 10;
  const radius = size === "small" ? 40 : 50;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;

  const getColor = (s: number) => {
    if (s >= 70) return "#22c55e";
    if (s >= 50) return "#eab308";
    if (s >= 30) return "#f97316";
    return "#ef4444";
  };

  return (
    <div className={cn("relative", dimensions)}>
      <svg className="w-full h-full transform -rotate-90" viewBox={size === "small" ? "0 0 100 100" : "0 0 120 120"}>
        <circle
          cx={size === "small" ? 50 : 60}
          cy={size === "small" ? 50 : 60}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-secondary"
        />
        <circle
          cx={size === "small" ? 50 : 60}
          cy={size === "small" ? 50 : 60}
          r={radius}
          fill="none"
          stroke={getColor(score)}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          strokeLinecap="round"
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn("font-bold", size === "small" ? "text-xl" : "text-3xl")}>{Math.round(score)}</span>
        <span className="text-xs text-muted-foreground">/ 100</span>
      </div>
    </div>
  );
}

function LeaguePageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isElite } = useAuth();

  // State
  const [view, setView] = useState<"connect" | "select" | "analysis">("connect");
  const [username, setUsername] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [leagues, setLeagues] = useState<SleeperLeague[]>([]);
  const [selectedLeagueId, setSelectedLeagueId] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<LeagueAnalysis | null>(null);
  const [activeTab, setActiveTab] = useState("overview");

  // Check for league ID in URL on mount
  useEffect(() => {
    const leagueId = searchParams.get("id");
    if (leagueId && isElite) {
      setSelectedLeagueId(leagueId);
      setView("analysis");
      fetchAnalysis(leagueId);
    }
  }, [searchParams, isElite]);

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const response = await api.connectSleeper(username.trim());
      setLeagues(response.leagues);
      setView("select");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect. Check your username.");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectLeague = async (leagueId: string) => {
    setSelectedLeagueId(leagueId);
    setView("analysis");
    router.push(`/league?id=${leagueId}`);
    await fetchAnalysis(leagueId);
  };

  const fetchAnalysis = async (leagueId: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.analyzeLeague(leagueId);
      setAnalysis(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to analyze league");
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    if (view === "analysis") {
      setView("select");
      setAnalysis(null);
      router.push("/league");
    } else if (view === "select") {
      setView("connect");
      setLeagues([]);
    }
  };

  // Elite gate
  if (!isElite) {
    return (
      <div className="max-w-2xl mx-auto">
        <Card variant="glass" className="text-center">
          <CardHeader>
            <div className="mx-auto h-16 w-16 rounded-full bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center mb-4">
              <Trophy className="h-8 w-8 text-black" />
            </div>
            <CardTitle className="text-2xl">Premium League Analysis</CardTitle>
            <CardDescription className="text-base">
              Connect your Sleeper leagues for AI-powered dynasty analysis
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid grid-cols-2 gap-4 text-left">
              {[
                "Championship probability simulation",
                "Dynasty health score breakdown",
                "Trade radar with win-win suggestions",
                "Power rankings (KTC + ML-projected)",
                "Positional strength analysis",
                "Buy low / sell high candidates",
              ].map((feature) => (
                <div key={feature} className="flex items-center gap-2 text-sm">
                  <Sparkles className="h-4 w-4 text-amber-500 flex-shrink-0" />
                  <span>{feature}</span>
                </div>
              ))}
            </div>
            <div className="border-t border-border pt-6">
              <Button variant="premium" size="lg" asChild>
                <a href="/pricing">
                  <Crown className="h-4 w-4 mr-2" />
                  Upgrade to Elite
                </a>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Connect View
  if (view === "connect") {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Trophy className="h-6 w-6 text-amber-500" />
            League Analysis
          </h1>
          <p className="text-muted-foreground mt-1">Connect your Sleeper account for dynasty insights</p>
        </div>

        <Card variant="glass" className="max-w-xl mx-auto">
          <CardHeader className="text-center">
            <div className="mx-auto h-12 w-12 rounded-full bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center mb-2">
              <Users className="h-6 w-6 text-black" />
            </div>
            <CardTitle>Connect Sleeper</CardTitle>
            <CardDescription>Enter your Sleeper username to fetch your dynasty leagues</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleConnect} className="space-y-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Enter Sleeper username..."
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="pl-10"
                  disabled={loading}
                />
              </div>
              {error && (
                <div className="flex items-center gap-2 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4" />
                  {error}
                </div>
              )}
              <Button type="submit" className="w-full" disabled={loading || !username.trim()}>
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Connecting...
                  </>
                ) : (
                  <>
                    Connect Account
                    <ArrowRight className="h-4 w-4 ml-2" />
                  </>
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        <div className="grid md:grid-cols-3 gap-4 mt-8">
          {[
            { icon: Shield, title: "Championship Odds", desc: "Monte Carlo simulation of your season" },
            { icon: Users, title: "Trade Radar", desc: "Find win-win deals with league-mates" },
            { icon: Trophy, title: "Dynasty Health", desc: "Score your roster's long-term outlook" },
          ].map((feature) => (
            <Card key={feature.title} variant="elevated" className="p-4">
              <feature.icon className="h-8 w-8 text-amber-500 mb-2" />
              <h3 className="font-semibold">{feature.title}</h3>
              <p className="text-sm text-muted-foreground">{feature.desc}</p>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  // Select League View
  if (view === "select") {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Trophy className="h-6 w-6 text-amber-500" />
              Select League
            </h1>
            <p className="text-muted-foreground mt-1">Choose a league to analyze</p>
          </div>
          <Button variant="outline" onClick={handleBack}>
            Change Account
          </Button>
        </div>

        {leagues.length === 0 ? (
          <Card variant="glass" className="text-center py-12">
            <Trophy className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No Dynasty Leagues Found</h3>
            <p className="text-muted-foreground mb-4">We couldn&apos;t find any dynasty leagues for this account.</p>
            <Button variant="outline" onClick={handleBack}>
              Try Another Username
            </Button>
          </Card>
        ) : (
          <div className="grid gap-4">
            {leagues.map((league) => (
              <Card
                key={league.league_id}
                variant="glass"
                className="cursor-pointer hover:border-primary/50 transition-all hover:shadow-lg group"
                onClick={() => handleSelectLeague(league.league_id)}
              >
                <CardContent className="p-4">
                  <div className="flex items-center gap-4">
                    <div className="h-12 w-12 rounded-lg bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center">
                      <Trophy className="h-6 w-6 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold truncate group-hover:text-primary transition-colors">
                        {league.name}
                      </h3>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="secondary" className="text-xs">
                          {league.total_rosters} teams
                        </Badge>
                        <Badge variant="outline" className="text-xs">
                          {league.season}
                        </Badge>
                        <Badge
                          variant={league.status === "in_season" ? "success" : "secondary"}
                          className="text-xs"
                        >
                          {league.status === "in_season" ? "Active" : league.status}
                        </Badge>
                      </div>
                    </div>
                    <ChevronRight className="h-5 w-5 text-muted-foreground group-hover:text-primary group-hover:translate-x-1 transition-all" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Analysis View
  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px]">
        <Loader2 className="h-12 w-12 animate-spin text-primary mb-4" />
        <p className="text-lg font-medium">Analyzing league...</p>
        <p className="text-sm text-muted-foreground">Running Monte Carlo simulations</p>
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <Card variant="glass" className="max-w-md mx-auto text-center p-8">
        <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
        <h3 className="text-lg font-semibold mb-2">Analysis Failed</h3>
        <p className="text-muted-foreground mb-4">{error || "Unable to load league data"}</p>
        <div className="flex gap-2 justify-center">
          <Button variant="outline" onClick={handleBack}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
          <Button onClick={() => selectedLeagueId && fetchAnalysis(selectedLeagueId)}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </div>
      </Card>
    );
  }

  const { your_analysis: roster, your_dynasty_health: health, your_championship_odds: odds } = analysis;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <Button variant="ghost" size="sm" className="mb-2" onClick={handleBack}>
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to Leagues
          </Button>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Trophy className="h-6 w-6 text-amber-500" />
            {analysis.league_name}
          </h1>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant="outline">{analysis.season}</Badge>
            <Badge variant="secondary">{analysis.total_teams} teams</Badge>
            <Badge variant="secondary" className="capitalize">
              {analysis.scoring_type.replace("_", " ")}
            </Badge>
          </div>
        </div>
        <Button onClick={() => selectedLeagueId && fetchAnalysis(selectedLeagueId)} variant="outline">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Championship Odds"
          value={`${(odds.championship_probability * 100).toFixed(1)}%`}
          subtitle={odds.most_likely_record}
          icon={Crown}
          variant={odds.championship_probability >= 0.15 ? "success" : odds.championship_probability >= 0.08 ? "warning" : "default"}
        />
        <StatCard
          title="Dynasty Health"
          value={Math.round(health.total_score)}
          subtitle="/ 100"
          icon={Heart}
          variant={health.total_score >= 70 ? "success" : health.total_score >= 50 ? "warning" : "danger"}
        />
        <StatCard title="Roster Value" value={roster.total_ktc_value.toLocaleString()} subtitle="KTC" icon={Zap} />
        <StatCard
          title="Classification"
          value={roster.classification}
          subtitle={`Rank #${analysis.power_rankings.find((r) => r.roster_id === roster.roster_id)?.rank || "-"}`}
          icon={Target}
          variant={roster.classification === "CONTENDER" ? "success" : roster.classification === "FRINGE" ? "warning" : "default"}
        />
      </div>

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid grid-cols-5 w-full max-w-2xl">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="rankings">Rankings</TabsTrigger>
          <TabsTrigger value="trades">Trades</TabsTrigger>
          <TabsTrigger value="roster">Roster</TabsTrigger>
          <TabsTrigger value="health">Health</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6 mt-6">
          <div className="grid lg:grid-cols-3 gap-6">
            <Card variant="glass">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Heart className="h-5 w-5 text-rose-500" />
                  Dynasty Health
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col items-center">
                <HealthGauge score={health.total_score} />
                <div className="mt-4 w-full space-y-2">
                  {[
                    { label: "Age", score: health.age_score, max: 25 },
                    { label: "Peak Overlap", score: health.peak_overlap_score, max: 20 },
                    { label: "Position Wins", score: health.position_wins_score, max: 25 },
                    { label: "Draft Capital", score: health.draft_capital_score, max: 15 },
                    { label: "Injury Risk", score: health.injury_risk_score, max: 15 },
                  ].map((item) => (
                    <div key={item.label} className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground w-24">{item.label}</span>
                      <Progress value={(item.score / item.max) * 100} className="flex-1 h-1.5" />
                      <span className="text-xs font-medium w-8 text-right">{item.score}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card variant="glass">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Crown className="h-5 w-5 text-amber-500" />
                  Championship Odds
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="text-center">
                  <p className="text-4xl font-bold text-primary">{(odds.championship_probability * 100).toFixed(1)}%</p>
                  <p className="text-sm text-muted-foreground">to win it all</p>
                </div>
                <div className="space-y-3">
                  {[
                    { label: "Make Playoffs", value: odds.playoff_probability },
                    { label: "Get Bye Week", value: odds.bye_probability },
                    { label: "Win Championship", value: odds.championship_probability },
                  ].map((item) => (
                    <div key={item.label}>
                      <div className="flex justify-between text-sm mb-1">
                        <span>{item.label}</span>
                        <span className="font-medium">{(item.value * 100).toFixed(0)}%</span>
                      </div>
                      <Progress value={item.value * 100} />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card variant="glass">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Users className="h-5 w-5 text-sky-500" />
                  Positional Strength
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {roster.positional_strength.map((pos) => (
                    <div key={pos.position} className="flex items-center gap-3">
                      <Badge className={cn("w-10 justify-center", positionColors[pos.position])}>{pos.position}</Badge>
                      <div className="flex-1">
                        <div className="flex justify-between mb-1">
                          <span className="text-sm">{pos.player_count} players</span>
                          <span className={cn("text-sm font-bold", gradeColors[pos.grade])}>{pos.grade}</span>
                        </div>
                        <Progress value={Math.min(100, (pos.total_value / 30000) * 100)} className="h-1.5" />
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {(health.strengths.length > 0 || health.weaknesses.length > 0) && (
            <div className="grid md:grid-cols-2 gap-4">
              {health.strengths.length > 0 && (
                <Card variant="glass" className="border-l-4 border-l-emerald-500">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-emerald-600 flex items-center gap-2">
                      <ChevronUp className="h-4 w-4" />
                      Strengths
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-1">
                      {health.strengths.map((s, i) => (
                        <li key={i} className="text-sm flex items-start gap-2">
                          <Sparkles className="h-3 w-3 text-emerald-500 mt-1 flex-shrink-0" />
                          {s}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}
              {health.weaknesses.length > 0 && (
                <Card variant="glass" className="border-l-4 border-l-amber-500">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-amber-600 flex items-center gap-2">
                      <ChevronDown className="h-4 w-4" />
                      Areas to Improve
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-1">
                      {health.weaknesses.map((w, i) => (
                        <li key={i} className="text-sm flex items-start gap-2">
                          <AlertCircle className="h-3 w-3 text-amber-500 mt-1 flex-shrink-0" />
                          {w}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </TabsContent>

        {/* Rankings Tab */}
        <TabsContent value="rankings" className="mt-6">
          <Card variant="glass">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Trophy className="h-5 w-5 text-amber-500" />
                Power Rankings
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {analysis.power_rankings.map((team) => (
                  <div
                    key={team.roster_id}
                    className={cn(
                      "flex items-center gap-4 p-3 rounded-lg",
                      team.roster_id === roster.roster_id ? "bg-primary/10 border border-primary/30" : "bg-secondary/30"
                    )}
                  >
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-background font-bold">{team.rank}</div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">
                        {team.team_name}
                        {team.roster_id === roster.roster_id && (
                          <Badge variant="outline" className="ml-2 text-xs">
                            You
                          </Badge>
                        )}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <Badge className={cn("text-xs", classificationColors[team.classification])}>{team.classification}</Badge>
                        <span className="text-xs text-muted-foreground">{team.ktc_value.toLocaleString()} KTC</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-bold text-primary">{(team.championship_probability * 100).toFixed(1)}%</p>
                      <p className="text-xs text-muted-foreground">to win</p>
                    </div>
                    <HealthGauge score={team.dynasty_health_score} size="small" />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Trades Tab */}
        <TabsContent value="trades" className="mt-6 space-y-6">
          {analysis.top_trade_suggestions.length > 0 && (
            <Card variant="glass">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ArrowLeftRight className="h-5 w-5 text-primary" />
                  Suggested Trades
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {analysis.top_trade_suggestions.slice(0, 5).map((trade, i) => (
                  <div key={i} className="p-4 rounded-lg bg-secondary/30 space-y-3">
                    <div className="flex items-center justify-between">
                      <Badge
                        variant={
                          trade.value_differential > 0 ? "success" : trade.value_differential < 0 ? "destructive" : "secondary"
                        }
                      >
                        {trade.value_differential > 0 ? "+" : ""}
                        {trade.value_differential.toLocaleString()} value
                      </Badge>
                      <Badge variant="outline">{trade.win_win_score.toFixed(0)}% win-win</Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">You Give</p>
                        {trade.give_players.map((p) => (
                          <div key={p.player_id} className="flex items-center gap-2">
                            <Badge className={cn("text-xs", positionColors[p.position])}>{p.position}</Badge>
                            <span className="text-sm font-medium">{p.name}</span>
                          </div>
                        ))}
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">You Get</p>
                        {trade.get_players.map((p) => (
                          <div key={p.player_id} className="flex items-center gap-2">
                            <Badge className={cn("text-xs", positionColors[p.position])}>{p.position}</Badge>
                            <span className="text-sm font-medium">{p.name}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground">{trade.rationale}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {analysis.trade_partners.length > 0 && (
            <Card variant="glass">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5 text-sky-500" />
                  Best Trade Partners
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {analysis.trade_partners.map((partner) => (
                  <div key={partner.roster_id} className="flex items-center gap-4 p-3 rounded-lg bg-secondary/30">
                    <div className="flex-1">
                      <p className="font-medium">{partner.team_name}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-muted-foreground">Needs:</span>
                        {partner.weak_positions.slice(0, 3).map((pos) => (
                          <Badge key={pos} variant="outline" className="text-xs">
                            {pos}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-bold text-primary">{partner.compatibility_score}%</p>
                      <p className="text-xs text-muted-foreground">match</p>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Roster Tab */}
        <TabsContent value="roster" className="mt-6">
          <Card variant="glass">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5 text-sky-500" />
                Your Roster ({roster.team_name})
              </CardTitle>
              <CardDescription>
                {roster.players.length} players | {roster.total_ktc_value.toLocaleString()} KTC
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {["QB", "RB", "WR", "TE"].map((pos) => {
                  const posPlayers = roster.players.filter((p) => p.position === pos);
                  if (posPlayers.length === 0) return null;

                  return (
                    <div key={pos}>
                      <div className="flex items-center gap-2 mb-2">
                        <Badge className={cn(positionColors[pos])}>{pos}</Badge>
                        <span className="text-sm text-muted-foreground">{posPlayers.length} players</span>
                      </div>
                      <div className="grid gap-2">
                        {posPlayers
                          .sort((a, b) => b.ktc_value - a.ktc_value)
                          .map((player) => (
                            <div
                              key={player.player_id}
                              className={cn("flex items-center gap-3 p-2 rounded-lg", player.is_starter ? "bg-primary/5" : "bg-secondary/30")}
                            >
                              <div className="flex-1 min-w-0">
                                <p className="font-medium truncate">
                                  {player.name}
                                  {player.is_starter && (
                                    <Badge variant="secondary" className="ml-2 text-xs">
                                      Starter
                                    </Badge>
                                  )}
                                </p>
                                <div className="flex items-center gap-2 mt-0.5">
                                  <span className="text-xs text-muted-foreground">{player.team || "FA"}</span>
                                  {player.age && <span className="text-xs text-muted-foreground">Age {player.age}</span>}
                                  {player.career_phase && (
                                    <Badge variant="outline" className="text-xs">
                                      {player.career_phase}
                                    </Badge>
                                  )}
                                </div>
                              </div>
                              <div className="text-right">
                                <p className="font-semibold">{player.ktc_value.toLocaleString()}</p>
                                {player.projected_ppg && <p className="text-xs text-muted-foreground">{player.projected_ppg.toFixed(1)} PPG</p>}
                              </div>
                              {player.is_breakout_candidate && <TrendingUp className="h-4 w-4 text-emerald-500" />}
                              {player.is_sell_candidate && <TrendingDown className="h-4 w-4 text-amber-500" />}
                            </div>
                          ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Health Tab */}
        <TabsContent value="health" className="mt-6 space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            <Card variant="glass">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Heart className="h-5 w-5 text-rose-500" />
                  Dynasty Health Breakdown
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col items-center">
                <HealthGauge score={health.total_score} />
                <div className="mt-6 w-full space-y-4">
                  {[
                    { label: "Age Score", score: health.age_score, max: 25, desc: "Younger rosters score higher" },
                    { label: "Peak Overlap", score: health.peak_overlap_score, max: 20, desc: "Players peaking together" },
                    { label: "Position Wins", score: health.position_wins_score, max: 25, desc: "Positional strength grades" },
                    { label: "Draft Capital", score: health.draft_capital_score, max: 15, desc: "Future pick inventory" },
                    { label: "Injury Risk", score: health.injury_risk_score, max: 15, desc: "Lower risk = higher score" },
                  ].map((item) => (
                    <div key={item.label}>
                      <div className="flex justify-between mb-1">
                        <span className="text-sm font-medium">{item.label}</span>
                        <span className="text-sm">
                          {item.score} / {item.max}
                        </span>
                      </div>
                      <Progress value={(item.score / item.max) * 100} className="h-2" />
                      <p className="text-xs text-muted-foreground mt-0.5">{item.desc}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <div className="space-y-4">
              {health.recommendations.length > 0 && (
                <Card variant="glass">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-primary flex items-center gap-2">
                      <Target className="h-4 w-4" />
                      Recommendations
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2">
                      {health.recommendations.map((rec, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <ChevronRight className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                          {rec}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}

              <Card variant="glass">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <Trophy className="h-4 w-4 text-amber-500" />
                    Draft Capital
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold mb-2">{roster.draft_capital_value.toLocaleString()} KTC</div>
                  <div className="space-y-1">
                    {[2025, 2026, 2027].map((year) => {
                      const yearPicks = roster.future_picks.filter((p) => p.year === year);
                      if (yearPicks.length === 0) return null;
                      return (
                        <div key={year} className="flex items-center gap-2 text-sm">
                          <span className="w-12 font-medium">{year}</span>
                          <div className="flex gap-1">
                            {yearPicks.map((pick, i) => (
                              <Badge key={i} variant="outline" className="text-xs">
                                Rd {pick.round}
                              </Badge>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default function LeaguePage() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col items-center justify-center min-h-[400px]">
          <Loader2 className="h-12 w-12 animate-spin text-primary mb-4" />
          <p className="text-lg font-medium">Loading...</p>
        </div>
      }
    >
      <LeaguePageContent />
    </Suspense>
  );
}
