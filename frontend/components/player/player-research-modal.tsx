"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import {
  ChevronDown,
  ChevronUp,
  TrendingUp,
  TrendingDown,
  Minus,
  Activity,
  AlertTriangle,
  Calendar,
  Dumbbell,
  GraduationCap,
  BarChart3,
  Shield,
  Loader2,
} from "lucide-react";
import { api, PlayerResearch } from "@/lib/api";

interface PlayerResearchModalProps {
  playerId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// Reusable stat box component
function StatBox({
  label,
  value,
  unit = "",
  highlight = false,
}: {
  label: string;
  value?: number | string | null;
  unit?: string;
  highlight?: boolean;
}) {
  if (value === undefined || value === null) return null;
  const displayValue = typeof value === "number"
    ? (Number.isInteger(value) ? value : value.toFixed(1))
    : value;
  return (
    <div className={`text-center p-2 rounded ${highlight ? "bg-primary/10" : "bg-secondary/30"}`}>
      <p className="text-xs text-muted-foreground truncate">{label}</p>
      <p className={`font-medium text-sm ${highlight ? "text-primary" : ""}`}>
        {displayValue}{unit}
      </p>
    </div>
  );
}

// Trend indicator icon
function TrendIcon({ trend }: { trend?: string }) {
  if (trend === "rising") return <TrendingUp className="h-4 w-4 text-emerald-500" />;
  if (trend === "falling") return <TrendingDown className="h-4 w-4 text-rose-500" />;
  return <Minus className="h-4 w-4 text-muted-foreground" />;
}

// Grade badge with color coding
function GradeBadge({ grade }: { grade?: string }) {
  if (!grade) return null;
  const colors: Record<string, string> = {
    "A+": "bg-emerald-100 text-emerald-700 border-emerald-300",
    "A": "bg-emerald-100 text-emerald-600 border-emerald-200",
    "B+": "bg-sky-100 text-sky-700 border-sky-300",
    "B": "bg-sky-100 text-sky-600 border-sky-200",
    "C+": "bg-amber-100 text-amber-700 border-amber-300",
    "C": "bg-amber-100 text-amber-600 border-amber-200",
    "D": "bg-rose-100 text-rose-600 border-rose-200",
    "F": "bg-rose-100 text-rose-700 border-rose-300",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-bold border ${colors[grade] || "bg-secondary"}`}>
      {grade}
    </span>
  );
}

// Aging curve position badge
function AgingBadge({ position }: { position?: string }) {
  if (!position) return null;
  const colors: Record<string, string> = {
    "Pre-Peak": "bg-emerald-100 text-emerald-700",
    "Peak": "bg-sky-100 text-sky-700",
    "Post-Peak": "bg-amber-100 text-amber-700",
    "Declining": "bg-rose-100 text-rose-700",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[position] || "bg-secondary"}`}>
      {position}
    </span>
  );
}

// Risk level badge
function RiskBadge({ level }: { level?: string }) {
  if (!level) return null;
  const colors: Record<string, string> = {
    "Low": "bg-emerald-100 text-emerald-700",
    "Medium": "bg-amber-100 text-amber-700",
    "High": "bg-rose-100 text-rose-700",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[level] || "bg-secondary"}`}>
      {level} Risk
    </span>
  );
}

// Depth chart security badge
function DepthBadge({ security }: { security?: string }) {
  if (!security) return null;
  const colors: Record<string, string> = {
    "Locked": "bg-emerald-100 text-emerald-700",
    "Secure": "bg-sky-100 text-sky-700",
    "At Risk": "bg-rose-100 text-rose-700",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[security] || "bg-secondary"}`}>
      {security}
    </span>
  );
}

// Collapsible section component
function CollapsibleSection({
  title,
  icon: Icon,
  children,
  defaultOpen = false,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        className="w-full px-4 py-3 flex items-center justify-between bg-secondary/30 hover:bg-secondary/50 transition-colors"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-primary" />
          <span className="font-medium">{title}</span>
        </div>
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </button>
      {open && <div className="p-4">{children}</div>}
    </div>
  );
}

export function PlayerResearchModal({
  playerId,
  open,
  onOpenChange,
}: PlayerResearchModalProps) {
  const [player, setPlayer] = useState<PlayerResearch | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!playerId || !open) {
      setPlayer(null);
      setError(null);
      return;
    }

    const fetchPlayer = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.getPlayerResearch(playerId);
        if (response.success && response.data) {
          setPlayer(response.data);
        } else {
          setError("Failed to load player data");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load player data");
      } finally {
        setLoading(false);
      }
    };

    fetchPlayer();
  }, [playerId, open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <span className="ml-2 text-muted-foreground">Loading player data...</span>
          </div>
        )}

        {error && (
          <div className="flex items-center justify-center py-12">
            <AlertTriangle className="h-8 w-8 text-rose-500" />
            <span className="ml-2 text-rose-600">{error}</span>
          </div>
        )}

        {player && !loading && (
          <>
            {/* Header Section */}
            <DialogHeader className="pb-4 border-b border-border">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant={player.position.toLowerCase() as "qb" | "rb" | "wr" | "te"}>
                      {player.position}
                    </Badge>
                    <DialogTitle className="text-xl">{player.name}</DialogTitle>
                    <GradeBadge grade={player.overall_grade} />
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {player.team || "Free Agent"} | Age {player.age} | {player.experience || 0} yrs exp
                    {player.college && ` | ${player.college}`}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-mono font-bold text-2xl text-primary">
                    {player.value.current_value.toLocaleString()}
                  </p>
                  <div className="flex items-center gap-1 justify-end">
                    <TrendIcon trend={player.value.value_trend} />
                    <span className={`text-xs ${
                      player.value.value_30d_change && player.value.value_30d_change > 0
                        ? "text-emerald-600"
                        : player.value.value_30d_change && player.value.value_30d_change < 0
                        ? "text-rose-600"
                        : "text-muted-foreground"
                    }`}>
                      {player.value.value_30d_change != null
                        ? `${player.value.value_30d_change >= 0 ? "+" : ""}${player.value.value_30d_change.toFixed(1)}% 30d`
                        : "—"}
                    </span>
                  </div>
                  {player.value.value_rank && (
                    <p className="text-xs text-muted-foreground">
                      #{player.value.value_rank} overall
                      {player.value.positional_rank && ` | ${player.position}${player.value.positional_rank}`}
                    </p>
                  )}
                </div>
              </div>

              {/* One-liner summary */}
              {player.one_liner && (
                <p className="text-sm text-muted-foreground italic mt-3">
                  {player.one_liner}
                </p>
              )}
            </DialogHeader>

            {/* Collapsible Sections */}
            <div className="space-y-3 mt-4">
              {/* Value Analysis - Default Open */}
              <CollapsibleSection title="Value Analysis" icon={BarChart3} defaultOpen>
                <div className="space-y-4">
                  <div className="grid grid-cols-4 gap-2">
                    <StatBox label="Current" value={player.value.current_value.toLocaleString()} highlight />
                    <StatBox label="1yr Proj" value={player.value.projected_value_1yr?.toLocaleString()} />
                    <StatBox label="2yr Proj" value={player.value.projected_value_2yr?.toLocaleString()} />
                    <StatBox label="3yr Proj" value={player.value.projected_value_3yr?.toLocaleString()} />
                  </div>
                  {player.value.value_rank && (
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <span>Overall Rank: <strong className="text-foreground">#{player.value.value_rank}</strong></span>
                      {player.value.positional_rank && (
                        <span>Position Rank: <strong className="text-foreground">{player.position}{player.value.positional_rank}</strong></span>
                      )}
                    </div>
                  )}
                </div>
              </CollapsibleSection>

              {/* Production Metrics - Default Open */}
              <CollapsibleSection title="Production Metrics" icon={Activity} defaultOpen>
                <div className="space-y-4">
                  {/* Core Stats Row */}
                  <div className="grid grid-cols-4 gap-2">
                    <StatBox label="PPG (2024)" value={player.production.season_ppg} highlight />
                    <StatBox label="Games" value={player.production.games_played} />
                    <StatBox label="Total Pts" value={player.production.total_points} />
                    {player.position === "RB" ? (
                      <StatBox label="Touch%" value={player.production.touch_share} unit="%" />
                    ) : (
                      <StatBox label="Tgt%" value={player.production.target_share} unit="%" />
                    )}
                  </div>

                  {/* Receiving Stats (for WR/TE/RB) */}
                  {(player.production.targets || player.production.receptions) && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-2">Receiving</p>
                      <div className="grid grid-cols-5 gap-2">
                        <StatBox label="Targets" value={player.production.targets} />
                        <StatBox label="Rec" value={player.production.receptions} />
                        <StatBox label="Rec Yds" value={player.production.receiving_yards} />
                        <StatBox label="Rec TD" value={player.production.receiving_tds} />
                        <StatBox label="ADOT" value={player.production.adot} />
                      </div>
                    </div>
                  )}

                  {/* Rushing Stats (for RB/QB) */}
                  {(player.production.carries || player.production.rushing_yards) && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-2">Rushing</p>
                      <div className="grid grid-cols-4 gap-2">
                        <StatBox label="Carries" value={player.production.carries} />
                        <StatBox label="Rush Yds" value={player.production.rushing_yards} />
                        <StatBox label="Rush TD" value={player.production.rushing_tds} />
                        <StatBox label="Touch%" value={player.production.touch_share} unit="%" />
                      </div>
                    </div>
                  )}

                  {/* Efficiency Metrics */}
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-2">Efficiency</p>
                    <div className="grid grid-cols-4 gap-2">
                      <StatBox label="EPA/Touch" value={player.production.epa_per_touch} />
                      <StatBox label="RZ%" value={player.production.red_zone_share} unit="%" />
                      {player.position !== "RB" && <StatBox label="WOPR" value={player.production.wopr} />}
                      {player.position !== "RB" && player.production.adot && (
                        <StatBox label="ADOT" value={player.production.adot} />
                      )}
                    </div>
                  </div>
                </div>
              </CollapsibleSection>

              {/* Dynasty Outlook */}
              <CollapsibleSection title="Dynasty Outlook" icon={Calendar}>
                <div className="space-y-4">
                  <div className="flex items-center gap-4 flex-wrap">
                    <AgingBadge position={player.dynasty.aging_curve_position} />
                    {player.dynasty.years_in_peak !== undefined && player.dynasty.years_in_peak > 0 && (
                      <span className="text-sm text-muted-foreground">
                        {player.dynasty.years_in_peak} years remaining in peak
                      </span>
                    )}
                    {player.dynasty.peak_window && (
                      <span className="text-sm">
                        Peak Window: <strong>{player.dynasty.peak_window}</strong>
                      </span>
                    )}
                  </div>

                  {/* ML Projections */}
                  {(player.dynasty.projected_ppg || player.dynasty.projection_floor) && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-2">ML Season Projections</p>
                      <div className="grid grid-cols-4 gap-2">
                        <StatBox label="Projected PPG" value={player.dynasty.projected_ppg} highlight />
                        <StatBox label="Floor" value={player.dynasty.projection_floor} />
                        <StatBox label="Ceiling" value={player.dynasty.projection_ceiling} />
                        <StatBox
                          label="Confidence"
                          value={player.dynasty.projection_confidence
                            ? `${(player.dynasty.projection_confidence * 100).toFixed(0)}%`
                            : null}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </CollapsibleSection>

              {/* Risk Assessment */}
              <CollapsibleSection title="Risk Assessment" icon={Shield}>
                <div className="space-y-4">
                  <div className="flex items-center gap-4 flex-wrap">
                    <RiskBadge level={player.risk.injury_risk_level} />
                    <DepthBadge security={player.risk.depth_chart_security} />
                  </div>

                  <div className="grid grid-cols-3 gap-2">
                    <StatBox label="Injury Burden" value={player.risk.injury_burden_score} />
                    <StatBox label="Games Missed (3yr)" value={player.risk.games_missed_3yr} />
                    <StatBox label="Starter Rate" value={player.risk.starter_rate} unit="%" />
                  </div>
                </div>
              </CollapsibleSection>

              {/* Athletic Profile - Collapsed by default */}
              {player.athletic && (
                <CollapsibleSection title="Athletic Profile" icon={Dumbbell}>
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      {/* Physical */}
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-2">Physical</p>
                        <div className="grid grid-cols-2 gap-2">
                          <StatBox
                            label="Height"
                            value={player.athletic.height
                              ? `${Math.floor(player.athletic.height / 12)}'${player.athletic.height % 12}"`
                              : null}
                          />
                          <StatBox label="Weight" value={player.athletic.weight} unit=" lbs" />
                        </div>
                      </div>

                      {/* Speed */}
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-2">Speed & Agility</p>
                        <div className="grid grid-cols-2 gap-2">
                          <StatBox label="40-Yard" value={player.athletic.forty_time} unit="s" />
                          <StatBox label="3-Cone" value={player.athletic.three_cone} unit="s" />
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-4 gap-2">
                      <StatBox label="Vertical" value={player.athletic.vertical_jump} unit='"' />
                      <StatBox label="Broad" value={player.athletic.broad_jump} unit='"' />
                      <StatBox label="Shuttle" value={player.athletic.shuttle} unit="s" />
                      <StatBox label="Bench" value={player.athletic.bench_press} unit=" reps" />
                    </div>
                  </div>
                </CollapsibleSection>
              )}

              {/* Draft Capital - Collapsed by default */}
              {player.athletic && (player.athletic.draft_year || player.athletic.draft_round) && (
                <CollapsibleSection title="Draft Capital" icon={GraduationCap}>
                  <div className="flex items-center gap-6 text-sm">
                    {player.athletic.draft_year && (
                      <div>
                        <span className="text-muted-foreground">Draft Year: </span>
                        <strong>{player.athletic.draft_year}</strong>
                      </div>
                    )}
                    {player.athletic.draft_round && (
                      <div>
                        <span className="text-muted-foreground">Round: </span>
                        <strong>{player.athletic.draft_round}</strong>
                      </div>
                    )}
                    {player.athletic.draft_pick && (
                      <div>
                        <span className="text-muted-foreground">Pick: </span>
                        <strong>#{player.athletic.draft_pick}</strong>
                      </div>
                    )}
                    {player.college && (
                      <div>
                        <span className="text-muted-foreground">College: </span>
                        <strong>{player.college}</strong>
                      </div>
                    )}
                  </div>
                </CollapsibleSection>
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
