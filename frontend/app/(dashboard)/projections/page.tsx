"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  LineChart,
  Sparkles,
  Brain,
  Calendar,
  Target,
  RefreshCw,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Loader2,
} from "lucide-react";
import Link from "next/link";
import { api, Projection } from "@/lib/api";
import { useAuth } from "@/contexts/auth-context";

// Position filter options
const POSITIONS = ["ALL", "QB", "RB", "WR", "TE"] as const;
type PositionFilter = (typeof POSITIONS)[number];

// Position color styling
const positionColors: Record<string, string> = {
  QB: "bg-amber-500/15 text-amber-600 border-amber-500/30",
  RB: "bg-emerald-500/15 text-emerald-600 border-emerald-500/30",
  WR: "bg-sky-500/15 text-sky-600 border-sky-500/30",
  TE: "bg-purple-500/15 text-purple-600 border-purple-500/30",
};

// Loading skeleton component
function TableSkeleton() {
  return (
    <div className="animate-pulse space-y-3">
      {[...Array(8)].map((_, i) => (
        <div key={i} className="flex gap-4 py-3">
          <div className="h-4 w-8 bg-muted rounded" />
          <div className="h-4 w-32 bg-muted rounded" />
          <div className="h-4 w-12 bg-muted rounded" />
          <div className="h-4 w-12 bg-muted rounded" />
          <div className="h-4 w-16 bg-muted rounded" />
          <div className="h-4 w-16 bg-muted rounded" />
          <div className="h-4 w-16 bg-muted rounded" />
        </div>
      ))}
    </div>
  );
}

// Stats skeleton
function StatsSkeleton() {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {[...Array(4)].map((_, i) => (
        <Card key={i} variant="glass">
          <CardContent className="p-4 text-center animate-pulse">
            <div className="h-8 w-16 bg-muted rounded mx-auto mb-2" />
            <div className="h-3 w-20 bg-muted rounded mx-auto" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// Loading fallback for Suspense
function ProjectionsLoading() {
  return (
    <div className="space-y-8">
      <div className="flex items-center gap-3 mb-2">
        <div className="h-10 w-10 rounded-xl bg-purple-500/15 flex items-center justify-center">
          <Loader2 className="h-5 w-5 text-purple-600 animate-spin" />
        </div>
        <div className="flex items-center gap-2">
          <h1 className="text-3xl font-bold tracking-tight">ML Projections</h1>
          <Badge variant="elite">Elite</Badge>
        </div>
      </div>
      <p className="text-muted-foreground">Loading projections...</p>
    </div>
  );
}

// Main page wrapper with Suspense
export default function ProjectionsPage() {
  return (
    <Suspense fallback={<ProjectionsLoading />}>
      <ProjectionsContent />
    </Suspense>
  );
}

function ProjectionsContent() {
  const { isElite, loading: authLoading } = useAuth();

  // State management
  const [projections, setProjections] = useState<Projection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPosition, setSelectedPosition] = useState<PositionFilter>("ALL");
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [modelInfo, setModelInfo] = useState<{
    r_squared: number;
    training_samples: string;
    features: number;
  } | null>(null);

  const limit = 25;

  // Fetch projections from API
  const fetchProjections = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const params: {
        position?: string;
        limit: number;
        offset: number;
        sort_by: 'projected_points' | 'projected_ppg' | 'confidence';
      } = {
        limit,
        offset,
        sort_by: "projected_ppg",
      };

      if (selectedPosition !== "ALL") {
        params.position = selectedPosition;
      }

      const response = await api.getProjections(params);

      if (response.success !== false) {
        setProjections(response.data || []);
        setTotal(response.total || 0);
      } else {
        throw new Error("Failed to fetch projections");
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to load projections";
      setError(errorMessage);

      // If auth error or backend unavailable, show demo data
      if (errorMessage.includes("Authentication") || errorMessage.includes("fetch")) {
        setProjections(getDemoData(selectedPosition));
        setTotal(getDemoData(selectedPosition).length);
        setError("Using demo data - backend unavailable or authentication required");
      }
    } finally {
      setLoading(false);
    }
  }, [selectedPosition, offset]);

  // Fetch model info
  const fetchModelInfo = useCallback(async () => {
    try {
      const info = await api.getModelInfo();
      setModelInfo({
        r_squared: info.r_squared,
        training_samples: info.training_data?.samples || "9,414",
        features: 168,
      });
    } catch {
      // Use default values if model info unavailable
      setModelInfo({
        r_squared: 0.80,
        training_samples: "9,414",
        features: 168,
      });
    }
  }, []);

  // Fetch data on mount and when filters change
  useEffect(() => {
    if (isElite) {
      fetchProjections();
      fetchModelInfo();
    }
  }, [isElite, fetchProjections, fetchModelInfo]);

  // Reset offset when position changes
  useEffect(() => {
    setOffset(0);
  }, [selectedPosition]);

  // Show loading while auth is being checked
  if (authLoading) {
    return <ProjectionsLoading />;
  }

  // Non-Elite view - show upgrade prompt
  if (!isElite) {
    return (
      <div className="space-y-8">
        {/* Header */}
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-purple-500/15 flex items-center justify-center">
              <Brain className="h-5 w-5 text-purple-600" />
            </div>
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold tracking-tight">
                ML Projections
              </h1>
              <Badge variant="elite">Elite</Badge>
            </div>
          </div>
          <p className="text-muted-foreground">
            Season and weekly projections powered by our ensemble ML models.
          </p>
        </div>

        {/* Locked Content Preview */}
        <Card variant="premium" className="glow-gold">
          <CardContent className="py-16 text-center">
            <div className="max-w-md mx-auto">
              <div className="h-20 w-20 rounded-2xl bg-gradient-to-br from-purple-400 to-purple-600 flex items-center justify-center mx-auto mb-6 shadow-xl shadow-purple-500/25">
                <Brain className="h-10 w-10 text-white" />
              </div>
              <h2 className="text-2xl font-bold mb-3">Elite Feature</h2>
              <p className="text-muted-foreground mb-8 leading-relaxed">
                ML Projections are exclusive to Elite tier subscribers. Our
                ensemble model (R² = 0.80) provides season and weekly PPG
                projections for all skill positions.
              </p>
              <div className="flex flex-col sm:flex-row gap-3 justify-center">
                <Button variant="premium" size="lg" asChild>
                  <Link href="/pricing">
                    <Sparkles className="h-4 w-4 mr-2" />
                    Upgrade to Elite
                  </Link>
                </Button>
                <Button variant="outline" size="lg" asChild>
                  <Link href="/">Back to Dashboard</Link>
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Feature Preview */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          <Card variant="glass" className="opacity-70">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-purple-500/15 flex items-center justify-center">
                  <LineChart className="h-4 w-4 text-purple-600" />
                </div>
                Season Projections
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Full season PPG projections for 500+ players with confidence
                intervals.
              </p>
            </CardContent>
          </Card>
          <Card variant="glass" className="opacity-70">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-emerald-500/15 flex items-center justify-center">
                  <Calendar className="h-4 w-4 text-emerald-600" />
                </div>
                Weekly Projections
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Week-by-week projections accounting for matchups and injuries.
              </p>
            </CardContent>
          </Card>
          <Card variant="glass" className="opacity-70">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-sky-500/15 flex items-center justify-center">
                  <Target className="h-4 w-4 text-sky-600" />
                </div>
                Position Rankings
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Position-specific rankings based on projected production.
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Model Stats */}
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="text-lg">Model Performance</CardTitle>
            <CardDescription>
              Our ML ensemble achieves industry-leading accuracy
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center p-4 bg-secondary/50 rounded-xl">
                <p className="text-2xl font-bold text-purple-600">0.80</p>
                <p className="text-xs text-muted-foreground">R² Score</p>
              </div>
              <div className="text-center p-4 bg-secondary/50 rounded-xl">
                <p className="text-2xl font-bold text-sky-600">2.47</p>
                <p className="text-xs text-muted-foreground">RMSE (PPG)</p>
              </div>
              <div className="text-center p-4 bg-secondary/50 rounded-xl">
                <p className="text-2xl font-bold text-emerald-600">9,414</p>
                <p className="text-xs text-muted-foreground">Training Samples</p>
              </div>
              <div className="text-center p-4 bg-secondary/50 rounded-xl">
                <p className="text-2xl font-bold text-amber-500">168</p>
                <p className="text-xs text-muted-foreground">Features</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Elite user view - show actual projections
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <div className="h-10 w-10 rounded-xl bg-purple-500/15 flex items-center justify-center">
            <Brain className="h-5 w-5 text-purple-400" />
          </div>
          <div className="flex items-center gap-2">
            <h1 className="text-3xl font-bold tracking-tight">ML Projections</h1>
            <Badge variant="elite">Elite</Badge>
          </div>
        </div>
        <p className="text-muted-foreground">
          Season and weekly projections powered by our ensemble ML models.
        </p>
      </div>

      {/* Model Stats */}
      {loading && !modelInfo ? (
        <StatsSkeleton />
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card variant="glass">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-purple-600">
                {modelInfo?.r_squared?.toFixed(2) || "0.80"}
              </p>
              <p className="text-xs text-muted-foreground">R² Score</p>
            </CardContent>
          </Card>
          <Card variant="glass">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-sky-600">2.47</p>
              <p className="text-xs text-muted-foreground">RMSE (PPG)</p>
            </CardContent>
          </Card>
          <Card variant="glass">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-emerald-600">
                {modelInfo?.training_samples || "9,414"}
              </p>
              <p className="text-xs text-muted-foreground">Training Samples</p>
            </CardContent>
          </Card>
          <Card variant="glass">
            <CardContent className="p-4 text-center">
              <p className="text-2xl font-bold text-amber-500">
                {modelInfo?.features || 168}
              </p>
              <p className="text-xs text-muted-foreground">Features</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Position Filter */}
      <div className="flex items-center gap-2 flex-wrap">
        {POSITIONS.map((pos) => (
          <Button
            key={pos}
            variant={selectedPosition === pos ? "default" : "outline"}
            size="sm"
            onClick={() => setSelectedPosition(pos)}
            className={selectedPosition === pos ? "" : "hover:bg-secondary"}
          >
            {pos === "ALL" ? "All Positions" : pos}
          </Button>
        ))}
        <div className="ml-auto">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => fetchProjections()}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="flex items-center gap-3 p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl">
          <AlertCircle className="h-5 w-5 text-amber-600" />
          <p className="text-sm text-amber-700">{error}</p>
          <Button
            variant="outline"
            size="sm"
            className="ml-auto"
            onClick={() => fetchProjections()}
          >
            Retry
          </Button>
        </div>
      )}

      {/* Projections Table */}
      <Card variant="elevated">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <LineChart className="h-5 w-5 text-primary" />
            Season Projections (PPR)
          </CardTitle>
          <CardDescription>
            Full season PPG projections with 90% confidence intervals
            {total > 0 && ` • ${total} players`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <TableSkeleton />
          ) : projections.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <Brain className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No projections available for this position.</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border text-left text-sm text-muted-foreground">
                      <th className="pb-3 font-medium">Rank</th>
                      <th className="pb-3 font-medium">Player</th>
                      <th className="pb-3 font-medium">Pos</th>
                      <th className="pb-3 font-medium">Team</th>
                      <th className="pb-3 font-medium text-right">Proj PPG</th>
                      <th className="pb-3 font-medium text-right">Floor</th>
                      <th className="pb-3 font-medium text-right">Ceiling</th>
                      <th className="pb-3 font-medium text-right">Confidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50">
                    {projections.map((player, index) => (
                      <tr
                        key={player.player_id}
                        className="hover:bg-muted/30 transition-colors"
                      >
                        <td className="py-3 font-medium text-muted-foreground">
                          {player.projection_rank || offset + index + 1}
                        </td>
                        <td className="py-3 font-semibold">{player.name}</td>
                        <td className="py-3">
                          <span
                            className={`px-2 py-0.5 rounded text-xs font-medium border ${
                              positionColors[player.position] || "bg-secondary"
                            }`}
                          >
                            {player.position}
                          </span>
                        </td>
                        <td className="py-3 text-muted-foreground">
                          {player.team || "FA"}
                        </td>
                        <td className="py-3 text-right font-bold text-primary">
                          {player.projected_ppg?.toFixed(1) || "—"}
                        </td>
                        <td className="py-3 text-right text-muted-foreground">
                          {player.floor?.toFixed(1) || "—"}
                        </td>
                        <td className="py-3 text-right text-muted-foreground">
                          {player.ceiling?.toFixed(1) || "—"}
                        </td>
                        <td className="py-3 text-right">
                          <span
                            className={`px-2 py-0.5 rounded text-xs font-medium ${
                              (player.confidence || 0) >= 0.8
                                ? "bg-emerald-500/15 text-emerald-600"
                                : (player.confidence || 0) >= 0.6
                                ? "bg-amber-500/15 text-amber-600"
                                : "bg-rose-500/15 text-rose-600"
                            }`}
                          >
                            {((player.confidence || 0) * 100).toFixed(0)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {total > limit && (
                <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
                  <p className="text-sm text-muted-foreground">
                    Showing {offset + 1}-{Math.min(offset + limit, total)} of {total}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setOffset(Math.max(0, offset - limit))}
                      disabled={offset === 0}
                    >
                      <ChevronLeft className="h-4 w-4 mr-1" />
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setOffset(offset + limit)}
                      disabled={offset + limit >= total}
                    >
                      Next
                      <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Feature Cards */}
      <div className="grid md:grid-cols-3 gap-4">
        <Card variant="glass">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-purple-500/15 flex items-center justify-center">
                <LineChart className="h-4 w-4 text-purple-400" />
              </div>
              Season Projections
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Full season PPG projections for 500+ players with confidence intervals.
            </p>
          </CardContent>
        </Card>
        <Card variant="glass">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-emerald-500/15 flex items-center justify-center">
                <Calendar className="h-4 w-4 text-emerald-400" />
              </div>
              Weekly Projections
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Week-by-week projections accounting for matchups and injuries.
            </p>
          </CardContent>
        </Card>
        <Card variant="glass">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-sky-500/15 flex items-center justify-center">
                <Target className="h-4 w-4 text-sky-400" />
              </div>
              Position Rankings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Position-specific rankings based on projected production.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// Demo data fallback when backend is unavailable
function getDemoData(position: PositionFilter): Projection[] {
  const allData: Projection[] = [
    { player_id: "1", name: "Ja'Marr Chase", position: "WR", team: "CIN", age: 24, ktc_value: 9500, projected_points: 342, projected_ppg: 21.4, confidence: 0.89, ceiling: 24.6, floor: 18.2, projection_rank: 1 },
    { player_id: "2", name: "CeeDee Lamb", position: "WR", team: "DAL", age: 25, ktc_value: 9200, projected_points: 333, projected_ppg: 20.8, confidence: 0.87, ceiling: 23.7, floor: 17.9, projection_rank: 2 },
    { player_id: "3", name: "Tyreek Hill", position: "WR", team: "MIA", age: 30, ktc_value: 7800, projected_points: 314, projected_ppg: 19.6, confidence: 0.82, ceiling: 22.8, floor: 16.4, projection_rank: 3 },
    { player_id: "4", name: "Bijan Robinson", position: "RB", team: "ATL", age: 22, ktc_value: 9800, projected_points: 307, projected_ppg: 19.2, confidence: 0.85, ceiling: 22.3, floor: 16.1, projection_rank: 4 },
    { player_id: "5", name: "Breece Hall", position: "RB", team: "NYJ", age: 23, ktc_value: 8900, projected_points: 299, projected_ppg: 18.7, confidence: 0.83, ceiling: 21.6, floor: 15.8, projection_rank: 5 },
    { player_id: "6", name: "Amon-Ra St. Brown", position: "WR", team: "DET", age: 25, ktc_value: 8500, projected_points: 294, projected_ppg: 18.4, confidence: 0.86, ceiling: 21.2, floor: 15.6, projection_rank: 6 },
    { player_id: "7", name: "Josh Allen", position: "QB", team: "BUF", age: 28, ktc_value: 8200, projected_points: 387, projected_ppg: 24.2, confidence: 0.91, ceiling: 26.6, floor: 21.8, projection_rank: 7 },
    { player_id: "8", name: "Lamar Jackson", position: "QB", team: "BAL", age: 27, ktc_value: 7900, projected_points: 381, projected_ppg: 23.8, confidence: 0.88, ceiling: 26.7, floor: 20.9, projection_rank: 8 },
    { player_id: "9", name: "Jalen Hurts", position: "QB", team: "PHI", age: 26, ktc_value: 8100, projected_points: 372, projected_ppg: 23.3, confidence: 0.86, ceiling: 26.1, floor: 20.5, projection_rank: 9 },
    { player_id: "10", name: "Travis Kelce", position: "TE", team: "KC", age: 35, ktc_value: 5800, projected_points: 256, projected_ppg: 16.0, confidence: 0.79, ceiling: 18.8, floor: 13.2, projection_rank: 10 },
    { player_id: "11", name: "Sam LaPorta", position: "TE", team: "DET", age: 23, ktc_value: 7200, projected_points: 248, projected_ppg: 15.5, confidence: 0.75, ceiling: 18.2, floor: 12.8, projection_rank: 11 },
    { player_id: "12", name: "Jahmyr Gibbs", position: "RB", team: "DET", age: 22, ktc_value: 8700, projected_points: 285, projected_ppg: 17.8, confidence: 0.81, ceiling: 20.9, floor: 14.7, projection_rank: 12 },
    { player_id: "13", name: "Garrett Wilson", position: "WR", team: "NYJ", age: 24, ktc_value: 8300, projected_points: 278, projected_ppg: 17.4, confidence: 0.80, ceiling: 20.3, floor: 14.5, projection_rank: 13 },
    { player_id: "14", name: "A.J. Brown", position: "WR", team: "PHI", age: 27, ktc_value: 7600, projected_points: 275, projected_ppg: 17.2, confidence: 0.78, ceiling: 20.1, floor: 14.3, projection_rank: 14 },
    { player_id: "15", name: "Jonathan Taylor", position: "RB", team: "IND", age: 25, ktc_value: 7100, projected_points: 268, projected_ppg: 16.8, confidence: 0.76, ceiling: 19.7, floor: 13.9, projection_rank: 15 },
  ];

  if (position === "ALL") {
    return allData;
  }

  return allData
    .filter((p) => p.position === position)
    .map((p, i) => ({ ...p, projection_rank: i + 1 }));
}
