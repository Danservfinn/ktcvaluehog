"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  ArrowLeftRight,
  X,
  Search,
  Scale,
  AlertCircle,
  ArrowUpRight,
  ArrowDownRight,
  Sparkles,
  Loader2,
  Target,
  FileText,
} from "lucide-react";
import Link from "next/link";
import { api, PlayerSummary, EliteTradeAnalysis } from "@/lib/api";
import { useAuth } from "@/contexts/auth-context";
import { EliteTradeReport } from "@/components/trade/elite-trade-report";

type Player = {
  id: string;
  name: string;
  pos: string;
  team: string;
  value: number;
};

function PlayerSearchInput({
  onSelect,
  exclude,
}: {
  onSelect: (player: Player) => void;
  exclude: string[];
}) {
  const [search, setSearch] = useState("");
  const [showResults, setShowResults] = useState(false);
  const [results, setResults] = useState<Player[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (search.length < 2) {
      setResults([]);
      return;
    }

    const timeoutId = setTimeout(async () => {
      setLoading(true);
      try {
        const response = await api.searchPlayers({ q: search, limit: 8 });
        if (response.data) {
          const players = response.data
            .filter((p) => !exclude.includes(p.player_id))
            .map((p) => ({
              id: p.player_id,
              name: p.name,
              pos: p.position,
              team: p.team || "FA",
              value: p.ktc_value,
            }));
          setResults(players);
        }
      } catch (error) {
        console.error("Failed to search players:", error);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [search, exclude]);

  return (
    <div className="relative">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search player..."
          className="pl-9"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setShowResults(true);
          }}
          onFocus={() => setShowResults(true)}
        />
      </div>
      {showResults && (results.length > 0 || loading) && (
        <div className="absolute top-full left-0 right-0 z-10 mt-1 bg-card border border-border rounded-lg shadow-xl overflow-hidden">
          {loading ? (
            <div className="px-3 py-4 flex items-center justify-center">
              <Loader2 className="h-4 w-4 animate-spin text-primary mr-2" />
              <span className="text-sm text-muted-foreground">Searching...</span>
            </div>
          ) : (
            results.map((player) => (
              <button
                key={player.id}
                className="w-full px-3 py-2.5 text-left hover:bg-secondary/70 flex items-center justify-between transition-colors"
                onClick={() => {
                  onSelect(player);
                  setSearch("");
                  setShowResults(false);
                }}
              >
                <div className="flex items-center gap-2">
                  <Badge
                    variant={player.pos.toLowerCase() as "qb" | "rb" | "wr" | "te"}
                    className="w-10 justify-center"
                  >
                    {player.pos}
                  </Badge>
                  <span className="text-sm font-medium">{player.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {player.team}
                  </span>
                </div>
                <span className="text-sm font-mono text-muted-foreground">
                  {player.value.toLocaleString()}
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function TradeSide({
  title,
  players,
  onAdd,
  onRemove,
  exclude,
  variant,
  maxPlayers = 5,
}: {
  title: string;
  players: Player[];
  onAdd: (player: Player) => void;
  onRemove: (id: string) => void;
  exclude: string[];
  variant: "give" | "get";
  maxPlayers?: number;
}) {
  const total = players.reduce((sum, p) => sum + p.value, 0);
  const iconColor = variant === "give" ? "text-rose-500" : "text-emerald-500";
  const bgColor =
    variant === "give" ? "bg-rose-500/10" : "bg-emerald-500/10";

  return (
    <Card variant="glass" className="flex-1">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <div
            className={`h-8 w-8 rounded-lg ${bgColor} flex items-center justify-center`}
          >
            {variant === "give" ? (
              <ArrowUpRight className={`h-4 w-4 ${iconColor}`} />
            ) : (
              <ArrowDownRight className={`h-4 w-4 ${iconColor}`} />
            )}
          </div>
          {title}
        </CardTitle>
        <CardDescription>Add up to {maxPlayers} players</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {players.length < maxPlayers && (
          <PlayerSearchInput onSelect={onAdd} exclude={exclude} />
        )}
        <div className="space-y-2 min-h-[200px]">
          {players.map((player) => (
            <div
              key={player.id}
              className="flex items-center justify-between p-3 bg-secondary/50 rounded-lg border border-border/50 group"
            >
              <div className="flex items-center gap-2">
                <Badge
                  variant={player.pos.toLowerCase() as "qb" | "rb" | "wr" | "te"}
                  className="w-10 justify-center"
                >
                  {player.pos}
                </Badge>
                <span className="text-sm font-medium">{player.name}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-mono">
                  {player.value.toLocaleString()}
                </span>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={() => onRemove(player.id)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
          {players.length === 0 && (
            <div className="text-center py-12 text-muted-foreground text-sm">
              Search and add players above
            </div>
          )}
        </div>
        <div className="pt-3 border-t border-border">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Total Value</span>
            <span className="text-xl font-bold font-mono">
              {total.toLocaleString()}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function TradePage() {
  const { isElite } = useAuth();
  const [givePlayers, setGivePlayers] = useState<Player[]>([]);
  const [getPlayers, setGetPlayers] = useState<Player[]>([]);
  const [analyzed, setAnalyzed] = useState(false);
  const [eliteAnalysis, setEliteAnalysis] = useState<EliteTradeAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const giveTotal = givePlayers.reduce((sum, p) => sum + p.value, 0);
  const getTotal = getPlayers.reduce((sum, p) => sum + p.value, 0);
  const difference = getTotal - giveTotal;
  const percentDiff = giveTotal > 0 ? (difference / giveTotal) * 100 : 0;

  const allPlayerIds = [...givePlayers, ...getPlayers].map((p) => p.id);

  const handleAnalyze = async () => {
    if (givePlayers.length === 0 || getPlayers.length === 0) return;

    setAnalyzed(true);
    setError(null);

    // For Elite users, fetch the comprehensive analysis
    if (isElite) {
      setAnalyzing(true);
      try {
        const response = await api.analyzeTradeElite(
          givePlayers.map((p) => p.id),
          getPlayers.map((p) => p.id)
        );
        if (response.data) {
          setEliteAnalysis(response.data);
        }
      } catch (err) {
        console.error("Elite analysis failed:", err);
        setError(err instanceof Error ? err.message : "Failed to analyze trade");
      } finally {
        setAnalyzing(false);
      }
    }
  };

  const handleReset = () => {
    setGivePlayers([]);
    setGetPlayers([]);
    setAnalyzed(false);
    setEliteAnalysis(null);
    setError(null);
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <div className="h-10 w-10 rounded-xl bg-sky-500/15 flex items-center justify-center">
            <ArrowLeftRight className="h-5 w-5 text-sky-600" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Trade Analyzer</h1>
        </div>
        <p className="text-muted-foreground">
          Evaluate dynasty trades with KTC values. Free tier: 3 analyses/day.
        </p>
      </div>

      {/* Trade Builder */}
      <div className="grid md:grid-cols-2 gap-6">
        <TradeSide
          title="You Give"
          variant="give"
          players={givePlayers}
          onAdd={(p) => setGivePlayers([...givePlayers, p])}
          onRemove={(id) =>
            setGivePlayers(givePlayers.filter((p) => p.id !== id))
          }
          exclude={allPlayerIds}
        />
        <TradeSide
          title="You Get"
          variant="get"
          players={getPlayers}
          onAdd={(p) => setGetPlayers([...getPlayers, p])}
          onRemove={(id) =>
            setGetPlayers(getPlayers.filter((p) => p.id !== id))
          }
          exclude={allPlayerIds}
        />
      </div>

      {/* Actions */}
      <div className="flex gap-3 justify-center">
        <Button
          size="lg"
          variant="premium"
          onClick={handleAnalyze}
          disabled={givePlayers.length === 0 || getPlayers.length === 0}
        >
          <Scale className="h-5 w-5 mr-2" />
          Analyze Trade
        </Button>
        <Button size="lg" variant="outline" onClick={handleReset}>
          Reset
        </Button>
      </div>

      {/* Results */}
      {analyzed && (
        <>
          {/* Loading State for Elite Analysis */}
          {isElite && analyzing && (
            <Card variant="elevated" className="border-2 border-primary/20">
              <CardContent className="py-12">
                <div className="flex flex-col items-center justify-center gap-4">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  <div className="text-center">
                    <p className="font-medium">Generating Elite Trade Report</p>
                    <p className="text-sm text-muted-foreground">
                      Analyzing player data, projections, and aging curves...
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Error State */}
          {error && (
            <Card variant="elevated" className="border-2 border-rose-500/30">
              <CardContent className="py-6">
                <div className="flex items-start gap-3">
                  <AlertCircle className="h-5 w-5 text-rose-500 mt-0.5" />
                  <div>
                    <p className="font-medium text-rose-600">Analysis Failed</p>
                    <p className="text-sm text-muted-foreground mt-1">{error}</p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-3"
                      onClick={handleAnalyze}
                    >
                      Retry Analysis
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Elite Trade Report */}
          {isElite && eliteAnalysis && !analyzing && (
            <EliteTradeReport analysis={eliteAnalysis} />
          )}

          {/* Basic Analysis for non-Elite users or while Elite is loading */}
          {(!isElite || (!eliteAnalysis && !analyzing)) && !error && (
            <Card
              variant="elevated"
              className={`border-2 ${
                Math.abs(percentDiff) < 10
                  ? "border-sky-500/30"
                  : percentDiff > 0
                  ? "border-emerald-500/30"
                  : "border-rose-500/30"
              }`}
            >
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Target className="h-5 w-5 text-primary" />
                  Trade Analysis
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Summary */}
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <div className="text-center p-4 bg-secondary/50 rounded-xl">
                    <p className="text-xs text-muted-foreground mb-1">You Give</p>
                    <p className="text-xl font-bold font-mono">
                      {giveTotal.toLocaleString()}
                    </p>
                  </div>
                  <div className="text-center p-4 bg-secondary/50 rounded-xl">
                    <p className="text-xs text-muted-foreground mb-1">You Get</p>
                    <p className="text-xl font-bold font-mono">
                      {getTotal.toLocaleString()}
                    </p>
                  </div>
                  <div className="text-center p-4 bg-secondary/50 rounded-xl">
                    <p className="text-xs text-muted-foreground mb-1">Difference</p>
                    <p
                      className={`text-xl font-bold font-mono ${
                        difference >= 0 ? "text-emerald-600" : "text-rose-600"
                      }`}
                    >
                      {difference >= 0 ? "+" : ""}
                      {difference.toLocaleString()}
                    </p>
                  </div>
                  <div className="text-center p-4 bg-secondary/50 rounded-xl">
                    <p className="text-xs text-muted-foreground mb-1">% Diff</p>
                    <p
                      className={`text-xl font-bold ${
                        percentDiff >= 0 ? "text-emerald-600" : "text-rose-600"
                      }`}
                    >
                      {percentDiff >= 0 ? "+" : ""}
                      {percentDiff.toFixed(1)}%
                    </p>
                  </div>
                  <div className="text-center p-4 bg-secondary/50 rounded-xl">
                    <p className="text-xs text-muted-foreground mb-1">Verdict</p>
                    <Badge
                      variant={
                        Math.abs(percentDiff) < 10
                          ? "info"
                          : percentDiff > 0
                          ? "success"
                          : "error"
                      }
                      className="text-sm"
                    >
                      {Math.abs(percentDiff) < 10
                        ? "Fair"
                        : percentDiff > 0
                        ? "Win"
                        : "Lose"}
                    </Badge>
                  </div>
                </div>

                {/* Recommendation */}
                <div className="p-4 bg-secondary/30 rounded-xl border border-border">
                  <div className="flex items-start gap-3">
                    <AlertCircle
                      className={`h-5 w-5 mt-0.5 ${
                        Math.abs(percentDiff) < 10
                          ? "text-sky-600"
                          : percentDiff > 0
                          ? "text-emerald-600"
                          : "text-amber-600"
                      }`}
                    />
                    <div>
                      <p className="font-medium">
                        {Math.abs(percentDiff) < 10
                          ? "This trade is relatively fair"
                          : percentDiff > 0
                          ? "This trade favors you"
                          : "This trade favors the other side"}
                      </p>
                      <p className="text-sm text-muted-foreground mt-1">
                        {Math.abs(percentDiff) < 10
                          ? "Value difference is within 10%, making this a balanced trade."
                          : percentDiff > 0
                          ? `You're getting ${percentDiff.toFixed(0)}% more value. Consider accepting.`
                          : `You're giving up ${Math.abs(percentDiff).toFixed(0)}% more value. Try to get more back.`}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Upgrade CTA for non-Elite */}
                {!isElite && (
                  <Card variant="premium" className="glow-gold">
                    <CardContent className="p-4">
                      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                          <FileText className="h-5 w-5 text-amber-500" />
                          <div>
                            <p className="font-medium">
                              Want a comprehensive trade report?
                            </p>
                            <p className="text-sm text-muted-foreground">
                              Get ML projections, aging curves, risk analysis, and more.
                            </p>
                          </div>
                        </div>
                        <Button variant="premium" size="sm" asChild>
                          <Link href="/pricing">Upgrade to Elite</Link>
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
