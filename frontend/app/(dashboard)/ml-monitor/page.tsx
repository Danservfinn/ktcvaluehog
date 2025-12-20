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
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Brain,
  Activity,
  FlaskConical,
  Sparkles,
  RefreshCw,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Bot,
  Lightbulb,
  Target,
  TrendingUp,
  Zap,
  Database,
  Shield,
} from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import Link from "next/link";

// Types matching backend API
interface SystemStats {
  queue_size: number;
  total_experiments: number;
  completed: number;
  promoted: number;
  failed: number;
  rejected: number;
  avg_improvement: number;
  max_improvement: number;
  llm_connected: boolean;
}

interface AgentStatus {
  name: string;
  status: string;
  last_run: string | null;
  hypotheses_generated: number;
}

interface Hypothesis {
  id: string;
  type: string;
  description: string;
  priority: number;
  source: string;
  config: Record<string, unknown>;
  tags: string[];
}

interface Experiment {
  hypothesis_id: string;
  status: string;
  r2_improvement: number;
  rmse_improvement: number;
  duration_seconds: number;
  metrics: Record<string, number>;
}

interface LLMStatus {
  connected: boolean;
  url: string | null;
  model: string | null;
  cost: string | null;
}

interface MLMonitorData {
  stats: SystemStats;
  agents: AgentStatus[];
  top_hypotheses: Hypothesis[];
  recent_experiments: Experiment[];
  llm_status: LLMStatus;
  model_versions: number;
  last_updated: string;
}

// Agent icon mapping
const agentIcons: Record<string, typeof Brain> = {
  data_scout: Database,
  feature_engineer: FlaskConical,
  architecture_search: Brain,
  error_analyst: Target,
  drift_monitor: Activity,
  meta_learner: TrendingUp,
  llm_creative: Sparkles,
};

// Agent color mapping
const agentColors: Record<string, string> = {
  data_scout: "text-sky-500 bg-sky-500/15",
  feature_engineer: "text-emerald-500 bg-emerald-500/15",
  architecture_search: "text-purple-500 bg-purple-500/15",
  error_analyst: "text-rose-500 bg-rose-500/15",
  drift_monitor: "text-amber-500 bg-amber-500/15",
  meta_learner: "text-indigo-500 bg-indigo-500/15",
  llm_creative: "text-pink-500 bg-pink-500/15",
};

// Loading skeleton
function LoadingSkeleton() {
  return (
    <div className="space-y-8">
      <div className="flex items-center gap-3 mb-2">
        <div className="h-10 w-10 rounded-xl bg-purple-500/15 flex items-center justify-center">
          <Loader2 className="h-5 w-5 text-purple-600 animate-spin" />
        </div>
        <div className="flex items-center gap-2">
          <h1 className="text-3xl font-bold tracking-tight">ML Monitor</h1>
          <Badge variant="elite">Elite</Badge>
        </div>
      </div>
      <p className="text-muted-foreground">Loading autonomous ML system...</p>
    </div>
  );
}

// Main page wrapper with Suspense
export default function MLMonitorPage() {
  return (
    <Suspense fallback={<LoadingSkeleton />}>
      <MLMonitorContent />
    </Suspense>
  );
}

function MLMonitorContent() {
  const { isElite, loading: authLoading } = useAuth();
  const [data, setData] = useState<MLMonitorData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

  // Fetch ML monitor status
  const fetchStatus = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/api/v1/ml-monitor/status`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const result = await response.json();
      setData(result);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch status";
      setError(errorMessage);
      // Use demo data on error
      setData(getDemoData());
    } finally {
      setLoading(false);
    }
  }, [API_BASE]);

  // Trigger improvement cycle
  const triggerCycle = async (strategy: string) => {
    setActionLoading(`cycle-${strategy}`);
    try {
      await fetch(`${API_BASE}/api/v1/ml-monitor/run-cycle?strategy=${strategy}`, {
        method: "POST",
      });
      // Refresh after a short delay
      setTimeout(fetchStatus, 2000);
    } catch {
      setError("Failed to trigger cycle");
    } finally {
      setActionLoading(null);
    }
  };

  // Trigger specific agent
  const triggerAgent = async (agent: string) => {
    setActionLoading(`agent-${agent}`);
    try {
      await fetch(`${API_BASE}/api/v1/ml-monitor/run-agent?agent=${agent}`, {
        method: "POST",
      });
      setTimeout(fetchStatus, 2000);
    } catch {
      setError("Failed to trigger agent");
    } finally {
      setActionLoading(null);
    }
  };

  // Fetch on mount
  useEffect(() => {
    if (isElite) {
      fetchStatus();
      // Auto-refresh every 30 seconds
      const interval = setInterval(fetchStatus, 30000);
      return () => clearInterval(interval);
    }
  }, [isElite, fetchStatus]);

  // Show loading while auth is being checked
  if (authLoading) {
    return <LoadingSkeleton />;
  }

  // Non-Elite view
  if (!isElite) {
    return (
      <div className="space-y-8">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-purple-500/15 flex items-center justify-center">
              <Brain className="h-5 w-5 text-purple-600" />
            </div>
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold tracking-tight">ML Monitor</h1>
              <Badge variant="elite">Elite</Badge>
            </div>
          </div>
          <p className="text-muted-foreground">
            Monitor the autonomous ML improvement system.
          </p>
        </div>

        <Card variant="premium" className="glow-gold">
          <CardContent className="py-16 text-center">
            <div className="max-w-md mx-auto">
              <div className="h-20 w-20 rounded-2xl bg-gradient-to-br from-purple-400 to-purple-600 flex items-center justify-center mx-auto mb-6 shadow-xl shadow-purple-500/25">
                <Bot className="h-10 w-10 text-white" />
              </div>
              <h2 className="text-2xl font-bold mb-3">Elite Feature</h2>
              <p className="text-muted-foreground mb-8 leading-relaxed">
                The Autonomous ML System continuously improves model accuracy using 7
                specialized agents and your local LLM. Watch it discover new features,
                run experiments, and promote winning models.
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
      </div>
    );
  }

  // Elite view with data
  const stats = data?.stats;
  const agents = data?.agents || [];
  const hypotheses = data?.top_hypotheses || [];
  const experiments = data?.recent_experiments || [];
  const llmStatus = data?.llm_status;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-purple-500/15 flex items-center justify-center">
              <Bot className="h-5 w-5 text-purple-400" />
            </div>
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold tracking-tight">ML Monitor</h1>
              <Badge variant="elite">Elite</Badge>
            </div>
          </div>
          <p className="text-muted-foreground">
            Autonomous ML improvement system status and controls
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchStatus}
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
          <XCircle className="h-5 w-5 text-amber-600" />
          <p className="text-sm text-amber-700">{error}</p>
        </div>
      )}

      {/* Stats Cards - 5 items (Miller's Law) */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card variant="glass">
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-purple-600">{stats?.queue_size || 0}</p>
            <p className="text-xs text-muted-foreground">Queue Size</p>
          </CardContent>
        </Card>
        <Card variant="glass">
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-sky-600">{stats?.total_experiments || 0}</p>
            <p className="text-xs text-muted-foreground">Experiments</p>
          </CardContent>
        </Card>
        <Card variant="glass">
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-emerald-600">{stats?.completed || 0}</p>
            <p className="text-xs text-muted-foreground">Completed</p>
          </CardContent>
        </Card>
        <Card variant="glass">
          <CardContent className="p-4 text-center">
            <p className="text-2xl font-bold text-amber-500">{stats?.promoted || 0}</p>
            <p className="text-xs text-muted-foreground">Promoted</p>
          </CardContent>
        </Card>
        <Card variant="glass">
          <CardContent className="p-4 text-center">
            <div className="flex items-center justify-center gap-2">
              <div className={`h-3 w-3 rounded-full ${llmStatus?.connected ? "bg-emerald-500" : "bg-rose-500"}`} />
              <p className="text-sm font-medium">{llmStatus?.connected ? "Online" : "Offline"}</p>
            </div>
            <p className="text-xs text-muted-foreground">Local LLM</p>
          </CardContent>
        </Card>
      </div>

      {/* Improvement Stats */}
      {(stats?.avg_improvement || stats?.max_improvement) && (
        <div className="flex items-center gap-6 p-4 bg-gradient-to-r from-emerald-500/10 to-sky-500/10 rounded-xl border border-emerald-500/20">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-emerald-500" />
            <span className="text-sm text-muted-foreground">Avg Improvement:</span>
            <span className="font-bold text-emerald-600">
              +{((stats?.avg_improvement || 0) * 100).toFixed(2)}%
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-amber-500" />
            <span className="text-sm text-muted-foreground">Max Improvement:</span>
            <span className="font-bold text-amber-600">
              +{((stats?.max_improvement || 0) * 100).toFixed(2)}%
            </span>
          </div>
        </div>
      )}

      {/* Main Content Tabs */}
      <Tabs defaultValue="agents" className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="agents">Agents (7)</TabsTrigger>
          <TabsTrigger value="hypotheses">Queue ({hypotheses.length})</TabsTrigger>
          <TabsTrigger value="experiments">Experiments ({experiments.length})</TabsTrigger>
          <TabsTrigger value="controls">Controls</TabsTrigger>
        </TabsList>

        {/* Agents Tab - 7 agents (Miller's Law) */}
        <TabsContent value="agents">
          <Card variant="elevated">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Bot className="h-5 w-5 text-primary" />
                Autonomous Agents
              </CardTitle>
              <CardDescription>
                7 specialized agents working to improve model accuracy
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-4">
                {agents.map((agent) => {
                  const Icon = agentIcons[agent.name] || Brain;
                  const colorClass = agentColors[agent.name] || "text-gray-500 bg-gray-500/15";
                  const isRunning = actionLoading === `agent-${agent.name}`;

                  return (
                    <div
                      key={agent.name}
                      className="flex items-center gap-4 p-4 bg-secondary/50 rounded-xl hover:bg-secondary/70 transition-colors"
                    >
                      <div className={`h-10 w-10 rounded-lg flex items-center justify-center ${colorClass}`}>
                        <Icon className="h-5 w-5" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">
                          {agent.name.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                        </p>
                        <div className="flex items-center gap-2">
                          <Badge
                            variant={agent.status === "running" ? "success" : "secondary"}
                            className="text-2xs"
                          >
                            {agent.status}
                          </Badge>
                          {agent.hypotheses_generated > 0 && (
                            <span className="text-2xs text-muted-foreground">
                              {agent.hypotheses_generated} hypotheses
                            </span>
                          )}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => triggerAgent(agent.name)}
                        disabled={isRunning}
                      >
                        {isRunning ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Play className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Hypotheses Tab - Top 5 (Miller's Law) */}
        <TabsContent value="hypotheses">
          <Card variant="elevated">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Lightbulb className="h-5 w-5 text-amber-500" />
                Hypothesis Queue
              </CardTitle>
              <CardDescription>
                Top 5 pending hypotheses by priority
              </CardDescription>
            </CardHeader>
            <CardContent>
              {hypotheses.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <FlaskConical className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No hypotheses in queue. Run an agent to generate some.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {hypotheses.map((h, i) => (
                    <div
                      key={h.id}
                      className="p-4 bg-secondary/50 rounded-xl border border-border/50"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <Badge variant="outline" className="text-2xs">
                              {h.type}
                            </Badge>
                            <Badge
                              variant={h.source.includes("llm") ? "elite" : "secondary"}
                              className="text-2xs"
                            >
                              {h.source}
                            </Badge>
                          </div>
                          <p className="text-sm">{h.description}</p>
                        </div>
                        <div className="text-right">
                          <p className="text-lg font-bold text-primary">
                            {(h.priority * 100).toFixed(0)}
                          </p>
                          <p className="text-2xs text-muted-foreground">priority</p>
                        </div>
                      </div>
                      <Progress
                        value={h.priority * 100}
                        variant={h.priority > 0.7 ? "success" : h.priority > 0.4 ? "warning" : "default"}
                        className="mt-3 h-1"
                      />
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Experiments Tab - Top 5 (Miller's Law) */}
        <TabsContent value="experiments">
          <Card variant="elevated">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <FlaskConical className="h-5 w-5 text-emerald-500" />
                Recent Experiments
              </CardTitle>
              <CardDescription>
                Top 5 experiments by R² improvement
              </CardDescription>
            </CardHeader>
            <CardContent>
              {experiments.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <Activity className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No experiments run yet. Trigger a cycle to start.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-border text-left text-sm text-muted-foreground">
                        <th className="pb-3 font-medium">Hypothesis</th>
                        <th className="pb-3 font-medium">Status</th>
                        <th className="pb-3 font-medium text-right">R² Imp.</th>
                        <th className="pb-3 font-medium text-right">RMSE Imp.</th>
                        <th className="pb-3 font-medium text-right">Duration</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {experiments.map((exp, i) => (
                        <tr key={i} className="hover:bg-muted/30 transition-colors">
                          <td className="py-3 font-medium truncate max-w-[200px]">
                            {exp.hypothesis_id}
                          </td>
                          <td className="py-3">
                            <Badge
                              variant={
                                exp.status === "promoted"
                                  ? "success"
                                  : exp.status === "completed"
                                  ? "default"
                                  : exp.status === "failed"
                                  ? "destructive"
                                  : "secondary"
                              }
                              className="text-2xs"
                            >
                              {exp.status === "promoted" && <CheckCircle2 className="h-3 w-3 mr-1" />}
                              {exp.status === "failed" && <XCircle className="h-3 w-3 mr-1" />}
                              {exp.status}
                            </Badge>
                          </td>
                          <td className="py-3 text-right">
                            <span
                              className={
                                exp.r2_improvement > 0
                                  ? "text-emerald-600 font-medium"
                                  : "text-rose-600"
                              }
                            >
                              {exp.r2_improvement > 0 ? "+" : ""}
                              {(exp.r2_improvement * 100).toFixed(2)}%
                            </span>
                          </td>
                          <td className="py-3 text-right text-muted-foreground">
                            {exp.rmse_improvement > 0 ? "+" : ""}
                            {exp.rmse_improvement.toFixed(3)}
                          </td>
                          <td className="py-3 text-right text-muted-foreground">
                            <Clock className="h-3 w-3 inline mr-1" />
                            {exp.duration_seconds.toFixed(1)}s
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Controls Tab */}
        <TabsContent value="controls">
          <div className="grid md:grid-cols-2 gap-6">
            {/* Cycle Controls */}
            <Card variant="elevated">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Zap className="h-5 w-5 text-amber-500" />
                  Run Improvement Cycle
                </CardTitle>
                <CardDescription>
                  Trigger a full improvement cycle with a specific strategy
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {["exploration", "exploitation", "adversarial", "ensemble", "data-centric"].map(
                  (strategy) => {
                    const isRunning = actionLoading === `cycle-${strategy}`;
                    return (
                      <Button
                        key={strategy}
                        variant="outline"
                        className="w-full justify-start"
                        onClick={() => triggerCycle(strategy)}
                        disabled={isRunning}
                      >
                        {isRunning ? (
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                          <Play className="h-4 w-4 mr-2" />
                        )}
                        {strategy.charAt(0).toUpperCase() + strategy.slice(1)} Strategy
                      </Button>
                    );
                  }
                )}
              </CardContent>
            </Card>

            {/* LLM Status */}
            <Card variant="elevated">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-pink-500" />
                  Local LLM Status
                </CardTitle>
                <CardDescription>
                  Creative reasoning powered by your local LLM
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-xl">
                    <div className="flex items-center gap-3">
                      <div
                        className={`h-4 w-4 rounded-full ${
                          llmStatus?.connected ? "bg-emerald-500 animate-pulse" : "bg-rose-500"
                        }`}
                      />
                      <span className="font-medium">
                        {llmStatus?.connected ? "Connected" : "Disconnected"}
                      </span>
                    </div>
                    {llmStatus?.cost && (
                      <Badge variant="success" className="text-xs">
                        {llmStatus.cost}
                      </Badge>
                    )}
                  </div>

                  {llmStatus?.url && (
                    <div className="text-sm space-y-2">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">URL</span>
                        <span className="font-mono text-xs">{llmStatus.url}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Model</span>
                        <span className="font-mono text-xs">{llmStatus.model}</span>
                      </div>
                    </div>
                  )}

                  <div className="pt-4 border-t border-border">
                    <p className="text-sm text-muted-foreground">
                      The LLM Creative Agent uses your local LLM to brainstorm feature ideas,
                      generate code, and analyze prediction errors - all at $0 cost.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      {/* Last Updated */}
      {data?.last_updated && (
        <p className="text-xs text-muted-foreground text-center">
          Last updated: {new Date(data.last_updated).toLocaleString()}
        </p>
      )}
    </div>
  );
}

// Demo data for when backend is unavailable
function getDemoData(): MLMonitorData {
  return {
    stats: {
      queue_size: 27,
      total_experiments: 12,
      completed: 8,
      promoted: 3,
      failed: 1,
      rejected: 0,
      avg_improvement: 0.0045,
      max_improvement: 0.0123,
      llm_connected: true,
    },
    agents: [
      { name: "data_scout", status: "idle", last_run: null, hypotheses_generated: 3 },
      { name: "feature_engineer", status: "idle", last_run: null, hypotheses_generated: 12 },
      { name: "architecture_search", status: "idle", last_run: null, hypotheses_generated: 5 },
      { name: "error_analyst", status: "idle", last_run: null, hypotheses_generated: 2 },
      { name: "drift_monitor", status: "idle", last_run: null, hypotheses_generated: 0 },
      { name: "meta_learner", status: "idle", last_run: null, hypotheses_generated: 4 },
      { name: "llm_creative", status: "idle", last_run: null, hypotheses_generated: 6 },
    ],
    top_hypotheses: [
      {
        id: "feat_interaction_targets_x_snap_pct",
        type: "feature_engineering",
        description: "Add interaction feature: targets × snap_pct for usage intensity",
        priority: 0.85,
        source: "feature_engineer",
        config: {},
        tags: ["interaction", "usage"],
      },
      {
        id: "llm_offensive_line_strength",
        type: "new_feature",
        description: "Offensive line strength impacts RB opportunities and WR time to throw",
        priority: 0.78,
        source: "llm_creative",
        config: {},
        tags: ["llm", "contextual"],
      },
      {
        id: "data_refresh_pbp_2024",
        type: "data_refresh",
        description: "Play-by-play data is stale (last update: 2024-12-15)",
        priority: 0.72,
        source: "data_scout",
        config: {},
        tags: ["data", "freshness"],
      },
      {
        id: "arch_attention_heads_4",
        type: "architecture",
        description: "Increase attention heads from 2 to 4 for better feature interactions",
        priority: 0.68,
        source: "architecture_search",
        config: {},
        tags: ["neural", "attention"],
      },
      {
        id: "feat_ratio_ypc_vs_team",
        type: "feature_engineering",
        description: "Add ratio feature: yards per carry vs team average",
        priority: 0.62,
        source: "feature_engineer",
        config: {},
        tags: ["ratio", "relative"],
      },
    ],
    recent_experiments: [
      {
        hypothesis_id: "feat_interaction_targets_x_snap_pct",
        status: "promoted",
        r2_improvement: 0.0123,
        rmse_improvement: -0.045,
        duration_seconds: 45.2,
        metrics: {},
      },
      {
        hypothesis_id: "arch_ensemble_3_models",
        status: "completed",
        r2_improvement: 0.0089,
        rmse_improvement: -0.032,
        duration_seconds: 78.5,
        metrics: {},
      },
      {
        hypothesis_id: "feat_lag_ppg_3week",
        status: "promoted",
        r2_improvement: 0.0067,
        rmse_improvement: -0.028,
        duration_seconds: 32.1,
        metrics: {},
      },
      {
        hypothesis_id: "llm_target_share_efficiency",
        status: "completed",
        r2_improvement: 0.0045,
        rmse_improvement: -0.019,
        duration_seconds: 41.8,
        metrics: {},
      },
      {
        hypothesis_id: "data_refresh_injuries_2024",
        status: "failed",
        r2_improvement: -0.0012,
        rmse_improvement: 0.008,
        duration_seconds: 28.3,
        metrics: {},
      },
    ],
    llm_status: {
      connected: true,
      url: "http://172.16.108.209:1234",
      model: "openai/gpt-oss-20b",
      cost: "$0",
    },
    model_versions: 5,
    last_updated: new Date().toISOString(),
  };
}
