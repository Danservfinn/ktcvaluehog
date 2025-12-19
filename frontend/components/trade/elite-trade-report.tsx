"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ChevronDown,
  ChevronUp,
  TrendingUp,
  TrendingDown,
  Minus,
  Target,
  Shield,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  Zap,
  Activity,
  BarChart3,
  Users,
  Calendar,
} from "lucide-react";
import { EliteTradeAnalysis, ElitePlayerAnalysis, EliteTradeSide } from "@/lib/api";
import { WrittenReportSection } from "./written-report-section";

interface EliteTradeReportProps {
  analysis: EliteTradeAnalysis;
  givePlayers?: string[];
  getPlayers?: string[];
}

function VerdictBadge({ verdict, score }: { verdict: string; score: number }) {
  const variants = {
    WIN: { bg: "bg-emerald-100", text: "text-emerald-700", border: "border-emerald-300" },
    LOSE: { bg: "bg-rose-100", text: "text-rose-700", border: "border-rose-300" },
    FAIR: { bg: "bg-sky-100", text: "text-sky-700", border: "border-sky-300" },
  };
  const v = variants[verdict as keyof typeof variants] || variants.FAIR;

  return (
    <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full ${v.bg} ${v.border} border`}>
      <span className={`font-bold text-lg ${v.text}`}>{verdict}</span>
      <span className={`text-sm ${v.text}`}>
        ({score >= 0 ? "+" : ""}{score.toFixed(1)}%)
      </span>
    </div>
  );
}

function TrendIcon({ trend }: { trend?: string }) {
  if (trend === "rising") return <TrendingUp className="h-4 w-4 text-emerald-500" />;
  if (trend === "falling") return <TrendingDown className="h-4 w-4 text-rose-500" />;
  return <Minus className="h-4 w-4 text-muted-foreground" />;
}

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
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-bold border ${colors[grade] || "bg-secondary"}`}>
      {grade}
    </span>
  );
}

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

function StatBox({ label, value, unit = "", highlight = false }: { label: string; value?: number | string | null; unit?: string; highlight?: boolean }) {
  if (value === undefined || value === null) return null;
  const displayValue = typeof value === "number" ? value.toFixed(1) : value;
  return (
    <div className={`text-center p-2 rounded ${highlight ? "bg-primary/10" : "bg-secondary/30"}`}>
      <p className="text-xs text-muted-foreground truncate">{label}</p>
      <p className={`font-medium text-sm ${highlight ? "text-primary" : ""}`}>
        {displayValue}{unit}
      </p>
    </div>
  );
}

function PlayerCard({ player, variant }: { player: ElitePlayerAnalysis; variant: "give" | "get" }) {
  const [showDetails, setShowDetails] = useState(false);
  const borderColor = variant === "give" ? "border-rose-200" : "border-emerald-200";
  const bgColor = variant === "give" ? "bg-rose-50/50" : "bg-emerald-50/50";

  const hasProductionData = player.production.season_ppg || player.production.target_share || player.production.red_zone_share;
  const hasInjuryData = player.risk.injury_burden_score || player.risk.games_missed_3yr;
  const hasProjectionData = player.dynasty.projected_ppg || player.dynasty.projection_floor;

  return (
    <div className={`p-4 rounded-lg border ${borderColor} ${bgColor}`}>
      {/* Header Row */}
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <Badge variant={player.position.toLowerCase() as "qb" | "rb" | "wr" | "te"}>
              {player.position}
            </Badge>
            <span className="font-semibold">{player.name}</span>
            <GradeBadge grade={player.overall_grade} />
          </div>
          <p className="text-sm text-muted-foreground mt-1">{player.team || "FA"} | Age {player.age}</p>
        </div>
        <div className="text-right">
          <p className="font-mono font-bold">{player.value.current_value.toLocaleString()}</p>
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
                ? `${player.value.value_30d_change >= 0 ? "+" : ""}${player.value.value_30d_change.toFixed(0)}% 30d`
                : "—"}
            </span>
          </div>
        </div>
      </div>

      {/* One-liner */}
      <p className="text-sm text-muted-foreground italic mb-3">{player.one_liner}</p>

      {/* Key Stats Grid - Always Visible */}
      <div className="grid grid-cols-4 gap-2 text-sm mb-3">
        <StatBox label="PPG" value={player.production.season_ppg} highlight />
        {player.position === "RB" ? (
          <StatBox label="Touch%" value={player.production.touch_share || player.production.target_share} unit="%" />
        ) : (
          <StatBox label="Tgt%" value={player.production.target_share} unit="%" />
        )}
        <StatBox label="RZ%" value={player.production.red_zone_share} unit="%" />
        <div className="text-center p-2 rounded bg-secondary/30">
          <p className="text-xs text-muted-foreground">Risk</p>
          <RiskBadge level={player.risk.injury_risk_level} />
        </div>
      </div>

      {/* Dynasty & Aging Row */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <AgingBadge position={player.dynasty.aging_curve_position} />
          {player.dynasty.years_in_peak !== undefined && player.dynasty.years_in_peak > 0 && (
            <span className="text-xs text-muted-foreground">{player.dynasty.years_in_peak}yr in peak</span>
          )}
        </div>
        {player.dynasty.projected_ppg && (
          <div className="text-xs">
            <span className="text-muted-foreground">ML Proj: </span>
            <span className="font-medium text-primary">{player.dynasty.projected_ppg.toFixed(1)} PPG</span>
          </div>
        )}
      </div>

      {/* Expandable Details Toggle */}
      {(hasProductionData || hasInjuryData || hasProjectionData) && (
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="w-full text-xs text-primary hover:text-primary/80 flex items-center justify-center gap-1 py-1"
        >
          {showDetails ? (
            <>
              <ChevronUp className="h-3 w-3" />
              Hide Details
            </>
          ) : (
            <>
              <ChevronDown className="h-3 w-3" />
              Show Details
            </>
          )}
        </button>
      )}

      {/* Expanded Details */}
      {showDetails && (
        <div className="mt-3 pt-3 border-t border-border/50 space-y-4">
          {/* Production Deep Dive */}
          {hasProductionData && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
                <Activity className="h-3 w-3" /> Production Metrics
              </p>
              <div className="grid grid-cols-3 gap-2">
                <StatBox label="Last 4 PPG" value={player.production.last_4_ppg} />
                <StatBox label="EPA/Touch" value={player.production.epa_per_touch} />
                {player.position !== "RB" && <StatBox label="WOPR" value={player.production.wopr} />}
                {player.position !== "RB" && <StatBox label="ADOT" value={player.production.adot} />}
                {player.position === "RB" && <StatBox label="Touch%" value={player.production.touch_share} unit="%" />}
                <StatBox label="Boom%" value={player.production.boom_rate} unit="%" />
                <StatBox label="Bust%" value={player.production.bust_rate} unit="%" />
              </div>
            </div>
          )}

          {/* Injury Profile */}
          {hasInjuryData && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
                <AlertTriangle className="h-3 w-3" /> Injury Profile
              </p>
              <div className="grid grid-cols-2 gap-2">
                <StatBox label="Burden Score" value={player.risk.injury_burden_score} />
                <StatBox label="Games Missed (3yr)" value={player.risk.games_missed_3yr} />
              </div>
              {player.risk.key_injury_concerns && (
                <p className="text-xs text-rose-600 mt-2 italic">{player.risk.key_injury_concerns}</p>
              )}
            </div>
          )}

          {/* ML Projections */}
          {hasProjectionData && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1">
                <Zap className="h-3 w-3" /> ML Projections
              </p>
              <div className="grid grid-cols-4 gap-2">
                <StatBox label="Projected" value={player.dynasty.projected_ppg} highlight />
                <StatBox label="Floor" value={player.dynasty.projection_floor} />
                <StatBox label="Ceiling" value={player.dynasty.projection_ceiling} />
                <StatBox
                  label="Confidence"
                  value={player.dynasty.projection_confidence ? `${(player.dynasty.projection_confidence * 100).toFixed(0)}%` : null}
                />
              </div>
              {player.dynasty.projected_pos_rank && (
                <p className="text-xs text-muted-foreground mt-1">
                  Projected {player.position}{player.dynasty.projected_pos_rank}
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Projected Values - Always Visible */}
      <div className="mt-3 pt-3 border-t border-border/50">
        <p className="text-xs text-muted-foreground mb-2">Projected KTC Value</p>
        <div className="flex gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">1yr: </span>
            <span className="font-mono">{player.value.projected_value_1yr?.toLocaleString() || "—"}</span>
          </div>
          <div>
            <span className="text-muted-foreground">2yr: </span>
            <span className="font-mono">{player.value.projected_value_2yr?.toLocaleString() || "—"}</span>
          </div>
          <div>
            <span className="text-muted-foreground">3yr: </span>
            <span className="font-mono">{player.value.projected_value_3yr?.toLocaleString() || "—"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function TradeSideSummary({ side, variant }: { side: EliteTradeSide; variant: "give" | "get" }) {
  const bgColor = variant === "give" ? "bg-rose-500/10" : "bg-emerald-500/10";
  const textColor = variant === "give" ? "text-rose-600" : "text-emerald-600";

  return (
    <div className={`p-4 rounded-lg ${bgColor}`}>
      <div className="flex items-center justify-between mb-4">
        <h4 className={`font-semibold ${textColor}`}>
          {variant === "give" ? "You Give" : "You Get"}
        </h4>
        <span className={`font-mono font-bold text-lg ${textColor}`}>
          {side.total_current_value.toLocaleString()}
        </span>
      </div>

      <div className="space-y-3">
        {side.players.map((player) => (
          <PlayerCard key={player.player_id} player={player} variant={variant} />
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-border/50 grid grid-cols-3 gap-4 text-sm">
        <div>
          <p className="text-xs text-muted-foreground">Avg Age</p>
          <p className="font-medium">{side.average_age?.toFixed(1) || "—"}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">1yr Projected</p>
          <p className="font-mono">{side.total_projected_value_1yr?.toLocaleString() || "—"}</p>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">3yr Projected</p>
          <p className="font-mono">{side.total_projected_value_3yr?.toLocaleString() || "—"}</p>
        </div>
      </div>
    </div>
  );
}

function ScoreBar({ label, value, max = 30 }: { label: string; value: number; max?: number }) {
  const isPositive = value >= 0;
  const width = Math.min(Math.abs(value) / max * 100, 100);
  const bgColor = isPositive ? "bg-emerald-500" : "bg-rose-500";

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className={`font-mono ${isPositive ? "text-emerald-600" : "text-rose-600"}`}>
          {isPositive ? "+" : ""}{value.toFixed(1)}%
        </span>
      </div>
      <div className="h-2 bg-secondary rounded-full overflow-hidden">
        <div
          className={`h-full ${bgColor} rounded-full transition-all`}
          style={{ width: `${width}%` }}
        />
      </div>
    </div>
  );
}

export function EliteTradeReport({ analysis, givePlayers = [], getPlayers = [] }: EliteTradeReportProps) {
  return (
    <div className="space-y-6">
      {/* Written Report Section - Research Paper Style */}
      {analysis.written_report && (
        <WrittenReportSection
          narrative={analysis.written_report}
          analysis={analysis}
          givePlayers={givePlayers}
          getPlayers={getPlayers}
        />
      )}

      {/* Executive Summary */}
      <Card variant="elevated" className="border-2 border-primary/20">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Target className="h-5 w-5 text-primary" />
              Trade Analysis Report
            </CardTitle>
            <VerdictBadge verdict={analysis.verdict} score={analysis.verdict_score} />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-lg">{analysis.executive_summary}</p>

          <div className="flex flex-wrap gap-4">
            <div className="flex items-center gap-2 px-3 py-2 bg-secondary/50 rounded-lg">
              <Activity className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">
                Confidence: <strong>{analysis.confidence.toFixed(0)}%</strong>
              </span>
            </div>
            <div className="flex items-center gap-2 px-3 py-2 bg-secondary/50 rounded-lg">
              <Users className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">
                Best For: <strong>{analysis.best_for}</strong>
              </span>
            </div>
            <div className="flex items-center gap-2 px-3 py-2 bg-secondary/50 rounded-lg">
              <Shield className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">
                Risk: <strong>{analysis.risk_level}</strong>
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Key Insights */}
      {analysis.key_insights.length > 0 && (
        <Card variant="glass">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Zap className="h-4 w-4 text-amber-500" />
              Key Insights
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {analysis.key_insights.map((insight, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span className="text-primary mt-0.5">•</span>
                  {insight}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Trade Sides Comparison */}
      <div className="grid md:grid-cols-2 gap-6">
        <TradeSideSummary side={analysis.give_side} variant="give" />
        <TradeSideSummary side={analysis.get_side} variant="get" />
      </div>

      {/* Collapsible Sections */}
      <div className="space-y-3">
        {/* Score Breakdown */}
        <CollapsibleSection title="Score Breakdown" icon={BarChart3} defaultOpen>
          <div className="space-y-4">
            <ScoreBar label="Current Value" value={analysis.score_breakdown.current_value_edge} />
            <ScoreBar label="3-Year Projected" value={analysis.score_breakdown.projected_value_edge} />
            <ScoreBar label="Age Factor" value={analysis.score_breakdown.age_edge} />
            <ScoreBar label="Production" value={analysis.score_breakdown.production_edge} />
            <div className="pt-4 border-t border-border">
              <div className="flex justify-between items-center">
                <span className="font-semibold">Total Edge</span>
                <span className={`font-mono font-bold text-lg ${
                  analysis.score_breakdown.total_edge >= 0 ? "text-emerald-600" : "text-rose-600"
                }`}>
                  {analysis.score_breakdown.total_edge >= 0 ? "+" : ""}
                  {analysis.score_breakdown.total_edge.toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        </CollapsibleSection>

        {/* Recommendations */}
        <CollapsibleSection title="Recommendations" icon={CheckCircle} defaultOpen>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <h5 className="font-medium text-emerald-600 flex items-center gap-2">
                <CheckCircle className="h-4 w-4" />
                Accept If
              </h5>
              <ul className="space-y-1">
                {analysis.recommendation_accept_if.map((item, i) => (
                  <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                    <span className="text-emerald-500 mt-0.5">+</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div className="space-y-2">
              <h5 className="font-medium text-rose-600 flex items-center gap-2">
                <XCircle className="h-4 w-4" />
                Decline If
              </h5>
              <ul className="space-y-1">
                {analysis.recommendation_decline_if.map((item, i) => (
                  <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                    <span className="text-rose-500 mt-0.5">-</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {analysis.suggested_additions && (
            <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <p className="text-sm text-amber-700 flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" />
                <strong>Suggested:</strong> {analysis.suggested_additions}
              </p>
            </div>
          )}
        </CollapsibleSection>

        {/* Dynasty Context */}
        <CollapsibleSection title="Dynasty Context" icon={Calendar}>
          <div className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <h5 className="text-sm font-medium mb-2">Peak Windows</h5>
                <div className="space-y-2">
                  {[...analysis.give_side.players, ...analysis.get_side.players].map((p) => (
                    <div key={p.player_id} className="flex items-center justify-between text-sm">
                      <span>{p.name}</span>
                      <span className="text-muted-foreground">{p.dynasty.peak_window}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <h5 className="text-sm font-medium mb-2">Aging Positions</h5>
                <div className="space-y-2">
                  {[...analysis.give_side.players, ...analysis.get_side.players].map((p) => (
                    <div key={p.player_id} className="flex items-center justify-between text-sm">
                      <span>{p.name}</span>
                      <AgingBadge position={p.dynasty.aging_curve_position} />
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {analysis.similar_trade_note && (
              <div className="p-3 bg-secondary/50 rounded-lg">
                <p className="text-sm text-muted-foreground italic">
                  {analysis.similar_trade_note}
                </p>
              </div>
            )}
          </div>
        </CollapsibleSection>
      </div>
    </div>
  );
}
