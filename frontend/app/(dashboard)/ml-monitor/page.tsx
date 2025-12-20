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
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
  Trophy,
  GitBranch,
  Cpu,
  BarChart3,
  AlertTriangle,
  Layers,
  Square,
  Plus,
  Trash2,
} from "lucide-react";
import { useAuth } from "@/contexts/auth-context";
import { HypothesisBuilder } from "@/components/ml/hypothesis-builder";
import Link from "next/link";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Area,
  AreaChart,
} from "recharts";

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

interface ContinuousStatus {
  running: boolean;
  pid: number | null;
  started_at: string | null;
  strategy: string | null;
  uptime_seconds: number | null;
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

// Agent color mapping - matching Thoth brand
const agentColors: Record<string, { bg: string; text: string; border: string }> = {
  data_scout: { bg: "bg-sky-500/10", text: "text-sky-500", border: "border-sky-500/20" },
  feature_engineer: { bg: "bg-emerald-500/10", text: "text-emerald-500", border: "border-emerald-500/20" },
  architecture_search: { bg: "bg-purple-500/10", text: "text-purple-500", border: "border-purple-500/20" },
  error_analyst: { bg: "bg-rose-500/10", text: "text-rose-500", border: "border-rose-500/20" },
  drift_monitor: { bg: "bg-amber-500/10", text: "text-amber-500", border: "border-amber-500/20" },
  meta_learner: { bg: "bg-indigo-500/10", text: "text-indigo-500", border: "border-indigo-500/20" },
  llm_creative: { bg: "bg-pink-500/10", text: "text-pink-500", border: "border-pink-500/20" },
};

// Custom tooltip for chart
function CustomTooltip({ active, payload, label }: any) {
  if (active && payload && payload.length) {
    return (
      <div className="bg-card/95 backdrop-blur-lg border border-border rounded-lg shadow-xl p-3">
        <p className="text-xs text-muted-foreground mb-1">Experiment #{label}</p>
        <p className="text-sm font-bold text-emerald-500">
          R² Improvement: +{(payload[0].value * 100).toFixed(2)}%
        </p>
      </div>
    );
  }
  return null;
}

// Stat card component
function StatCard({
  title,
  value,
  icon: Icon,
  color,
  subtitle,
}: {
  title: string;
  value: string | number;
  icon: typeof Brain;
  color: string;
  subtitle?: string;
}) {
  const colorClasses: Record<string, string> = {
    purple: "from-purple-500/20 to-purple-600/10 border-purple-500/30 text-purple-600",
    sky: "from-sky-500/20 to-sky-600/10 border-sky-500/30 text-sky-600",
    emerald: "from-emerald-500/20 to-emerald-600/10 border-emerald-500/30 text-emerald-600",
    amber: "from-amber-500/20 to-amber-600/10 border-amber-500/30 text-amber-600",
    rose: "from-rose-500/20 to-rose-600/10 border-rose-500/30 text-rose-600",
  };

  return (
    <div className={`relative overflow-hidden rounded-xl border bg-gradient-to-br ${colorClasses[color]} p-5`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-muted-foreground mb-1">{title}</p>
          <p className={`text-3xl font-bold tracking-tight ${colorClasses[color].split(" ").pop()}`}>
            {value}
          </p>
          {subtitle && (
            <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
          )}
        </div>
        <div className={`h-10 w-10 rounded-lg bg-white/50 flex items-center justify-center`}>
          <Icon className={`h-5 w-5 ${colorClasses[color].split(" ").pop()}`} />
        </div>
      </div>
    </div>
  );
}

// Loading skeleton
function LoadingSkeleton() {
  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-center gap-4">
        <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
          <Loader2 className="h-6 w-6 text-white animate-spin" />
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Autonomous ML System</h1>
          <p className="text-muted-foreground">Loading real-time monitoring data...</p>
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-28 rounded-xl bg-muted/50 animate-pulse" />
        ))}
      </div>
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

  // New state for controls
  const [continuousStatus, setContinuousStatus] = useState<ContinuousStatus | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState("exploration");
  const [selectedHypothesisId, setSelectedHypothesisId] = useState<string>("");
  const [showHypothesisBuilder, setShowHypothesisBuilder] = useState(false);

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
      setError(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch status";
      setError(errorMessage);
      setData(null);
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

  // Fetch continuous status
  const fetchContinuousStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/ml-monitor/continuous/status`);
      if (response.ok) {
        const result = await response.json();
        setContinuousStatus(result);
      }
    } catch {
      // Silently fail - not critical
    }
  };

  // Toggle continuous ML loop
  const toggleContinuous = async () => {
    setActionLoading("continuous");
    try {
      if (continuousStatus?.running) {
        await fetch(`${API_BASE}/api/v1/ml-monitor/continuous/stop`, {
          method: "POST",
        });
      } else {
        await fetch(`${API_BASE}/api/v1/ml-monitor/continuous/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            strategy: selectedStrategy,
            interval_seconds: 3600,
          }),
        });
      }
      await fetchContinuousStatus();
    } catch {
      setError("Failed to toggle continuous mode");
    } finally {
      setActionLoading(null);
    }
  };

  // Run a specific hypothesis
  const runHypothesis = async () => {
    if (!selectedHypothesisId) return;
    setActionLoading("run-hypothesis");
    try {
      await fetch(`${API_BASE}/api/v1/ml-monitor/hypothesis/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hypothesis_id: selectedHypothesisId }),
      });
      setTimeout(fetchStatus, 2000);
    } catch {
      setError("Failed to run hypothesis");
    } finally {
      setActionLoading(null);
      setSelectedHypothesisId("");
    }
  };

  // Delete a hypothesis
  const deleteHypothesis = async (hypothesisId: string) => {
    setActionLoading(`delete-${hypothesisId}`);
    try {
      await fetch(`${API_BASE}/api/v1/ml-monitor/hypothesis/${hypothesisId}`, {
        method: "DELETE",
      });
      await fetchStatus();
    } catch {
      setError("Failed to delete hypothesis");
    } finally {
      setActionLoading(null);
    }
  };

  // Submit new hypothesis
  const submitHypothesis = async (hypothesis: {
    type: string;
    description: string;
    priority: number;
    config: Record<string, unknown>;
    tags: string[];
  }) => {
    const response = await fetch(`${API_BASE}/api/v1/ml-monitor/hypothesis/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(hypothesis),
    });
    if (!response.ok) {
      throw new Error("Failed to submit hypothesis");
    }
    await fetchStatus();
  };

  // Format uptime
  const formatUptime = (seconds: number | null) => {
    if (!seconds) return "0s";
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    if (hours > 0) return `${hours}h ${mins}m`;
    if (mins > 0) return `${mins}m ${secs}s`;
    return `${secs}s`;
  };

  // Fetch on mount
  useEffect(() => {
    if (isElite) {
      fetchStatus();
      fetchContinuousStatus();
      const interval = setInterval(() => {
        fetchStatus();
        fetchContinuousStatus();
      }, 30000);
      return () => clearInterval(interval);
    }
  }, [isElite, fetchStatus]);

  if (authLoading) {
    return <LoadingSkeleton />;
  }

  // Non-Elite view
  if (!isElite) {
    return (
      <div className="space-y-8">
        <div className="flex items-center gap-4">
          <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-purple-500/25">
            <Bot className="h-6 w-6 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold tracking-tight">Autonomous ML System</h1>
              <Badge variant="elite">Elite</Badge>
            </div>
            <p className="text-muted-foreground">Self-improving machine learning pipeline</p>
          </div>
        </div>

        <Card variant="premium" className="glow-gold">
          <CardContent className="py-16 text-center">
            <div className="max-w-lg mx-auto">
              <div className="h-24 w-24 rounded-2xl bg-gradient-to-br from-purple-400 via-pink-500 to-purple-600 flex items-center justify-center mx-auto mb-6 shadow-2xl shadow-purple-500/30">
                <Brain className="h-12 w-12 text-white" />
              </div>
              <h2 className="text-2xl font-bold mb-3">Unlock Autonomous ML</h2>
              <p className="text-muted-foreground mb-8 leading-relaxed">
                Watch 7 specialized AI agents continuously discover features, run experiments,
                and improve model accuracy - all powered by your local LLM at $0 cost.
              </p>
              <div className="flex flex-col sm:flex-row gap-3 justify-center">
                <Button variant="premium" size="lg" asChild>
                  <Link href="/pricing">
                    <Sparkles className="h-4 w-4 mr-2" />
                    Upgrade to Elite
                  </Link>
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

  // Prepare chart data
  const chartData = experiments.map((exp, index) => ({
    experiment: index,
    r2: exp.r2_improvement,
    name: exp.hypothesis_id.slice(0, 12),
  })).reverse();

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-purple-500/25">
            <Bot className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Autonomous ML System</h1>
            <p className="text-muted-foreground">Real-time monitoring of the self-improving ML pipeline</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* LLM Status Indicator */}
          <div className={`flex items-center gap-2 px-4 py-2 rounded-full border ${
            llmStatus?.connected
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-600"
              : "bg-rose-500/10 border-rose-500/30 text-rose-600"
          }`}>
            <div className={`h-2.5 w-2.5 rounded-full ${llmStatus?.connected ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`} />
            <span className="text-sm font-medium">
              {llmStatus?.connected ? "Local LLM Connected" : "LLM Offline"}
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchStatus}
            disabled={loading}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Error State - No Data */}
      {error && !data && (
        <Card variant="elevated" className="border-rose-500/30 bg-rose-500/5">
          <CardContent className="py-12 text-center">
            <div className="max-w-md mx-auto">
              <div className="h-16 w-16 rounded-2xl bg-rose-500/15 flex items-center justify-center mx-auto mb-4">
                <AlertTriangle className="h-8 w-8 text-rose-500" />
              </div>
              <h3 className="text-lg font-semibold text-rose-600 mb-2">Cannot Connect to ML System</h3>
              <p className="text-sm text-muted-foreground mb-4">
                {error === "HTTP 404"
                  ? "The ML monitor endpoint is not available. Make sure the backend server is running with the ML monitor router enabled."
                  : `Error: ${error}`}
              </p>
              <div className="bg-secondary/50 rounded-lg p-4 text-left text-xs font-mono text-muted-foreground">
                <p className="mb-2">To start the backend with ML monitor:</p>
                <code className="text-primary">cd backend && uvicorn app.main:app --reload --port 8001</code>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={fetchStatus}
                className="mt-4"
                disabled={loading}
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
                Retry Connection
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats Cards - 5 items (Miller's Law) - Only show when data exists */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard
            title="Pending Hypotheses"
            value={stats?.queue_size || 0}
            icon={Lightbulb}
            color="purple"
          />
          <StatCard
            title="Completed"
            value={stats?.completed || 0}
            icon={CheckCircle2}
            color="sky"
          />
          <StatCard
            title="Promoted"
            value={stats?.promoted || 0}
            icon={Trophy}
            color="emerald"
            subtitle="Models deployed"
          />
          <StatCard
            title="Failed"
            value={stats?.failed || 0}
            icon={XCircle}
            color="rose"
          />
          <StatCard
            title="Model Versions"
            value={data?.model_versions || 0}
            icon={GitBranch}
            color="amber"
          />
        </div>
      )}

      {/* Main Content Grid - Only show when data exists */}
      {data && (
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Experiment Performance Chart - 2 columns */}
        <Card variant="elevated" className="lg:col-span-2">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-emerald-500/15 flex items-center justify-center">
                  <BarChart3 className="h-4 w-4 text-emerald-500" />
                </div>
                <CardTitle className="text-lg">Experiment Performance</CardTitle>
              </div>
              {stats?.avg_improvement ? (
                <Badge variant="success" className="text-xs">
                  Avg: +{(stats.avg_improvement * 100).toFixed(2)}% R²
                </Badge>
              ) : null}
            </div>
            <CardDescription>R² improvement over experiments</CardDescription>
          </CardHeader>
          <CardContent>
            {experiments.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-muted-foreground">
                <div className="text-center">
                  <FlaskConical className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No experiments run yet. Trigger a cycle to start.</p>
                </div>
              </div>
            ) : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorR2" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
                    <XAxis
                      dataKey="experiment"
                      stroke="hsl(var(--muted-foreground))"
                      fontSize={12}
                      tickLine={false}
                      axisLine={false}
                      label={{ value: 'Experiment #', position: 'bottom', fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                    />
                    <YAxis
                      stroke="hsl(var(--muted-foreground))"
                      fontSize={12}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(value) => `${(value * 100).toFixed(1)}%`}
                      label={{ value: 'R² Improvement', angle: -90, position: 'insideLeft', fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <ReferenceLine
                      y={0.003}
                      stroke="#f59e0b"
                      strokeDasharray="5 5"
                      label={{ value: 'Promotion Threshold', position: 'right', fontSize: 10, fill: '#f59e0b' }}
                    />
                    <Area
                      type="monotone"
                      dataKey="r2"
                      stroke="#10b981"
                      strokeWidth={2}
                      fill="url(#colorR2)"
                      dot={{ fill: '#10b981', strokeWidth: 2, r: 4 }}
                      activeDot={{ r: 6, fill: '#10b981', stroke: '#fff', strokeWidth: 2 }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Experiments - 1 column */}
        <Card variant="elevated">
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-amber-500/15 flex items-center justify-center">
                <Trophy className="h-4 w-4 text-amber-500" />
              </div>
              <CardTitle className="text-lg">Top Experiments</CardTitle>
            </div>
            <CardDescription>Best R² improvements</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {experiments.length === 0 ? (
              <div className="py-8 text-center text-muted-foreground">
                <Activity className="h-8 w-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No experiments yet</p>
              </div>
            ) : (
              experiments.slice(0, 5).map((exp, i) => (
                <div key={i} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-muted-foreground">{i + 1}.</span>
                      <span className="text-sm font-medium truncate max-w-[140px]">
                        {exp.hypothesis_id}
                      </span>
                    </div>
                    <Badge
                      variant={exp.status === "promoted" ? "success" : exp.status === "completed" ? "default" : "destructive"}
                      className="text-2xs"
                    >
                      {exp.status}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <Progress
                      value={Math.min(100, (exp.r2_improvement / 0.02) * 100)}
                      variant={exp.r2_improvement > 0.003 ? "success" : "default"}
                      className="h-2 flex-1"
                    />
                    <span className={`text-xs font-bold ${exp.r2_improvement > 0 ? "text-emerald-600" : "text-rose-600"}`}>
                      {exp.r2_improvement > 0 ? "+" : ""}{(exp.r2_improvement * 100).toFixed(2)}%
                    </span>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
      )}

      {/* Tabs for Details - Only show when data exists */}
      {data && (
      <Tabs defaultValue="agents" className="w-full">
        <TabsList className="grid w-full grid-cols-4 lg:w-auto lg:inline-grid">
          <TabsTrigger value="agents" className="gap-2">
            <Cpu className="h-4 w-4" />
            <span className="hidden sm:inline">Agents</span>
          </TabsTrigger>
          <TabsTrigger value="queue" className="gap-2">
            <Lightbulb className="h-4 w-4" />
            <span className="hidden sm:inline">Queue</span>
          </TabsTrigger>
          <TabsTrigger value="history" className="gap-2">
            <FlaskConical className="h-4 w-4" />
            <span className="hidden sm:inline">History</span>
          </TabsTrigger>
          <TabsTrigger value="controls" className="gap-2">
            <Zap className="h-4 w-4" />
            <span className="hidden sm:inline">Controls</span>
          </TabsTrigger>
        </TabsList>

        {/* Agents Tab */}
        <TabsContent value="agents" className="mt-6">
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {agents.map((agent) => {
              const Icon = agentIcons[agent.name] || Brain;
              const colors = agentColors[agent.name] || { bg: "bg-gray-500/10", text: "text-gray-500", border: "border-gray-500/20" };
              const isRunning = actionLoading === `agent-${agent.name}`;

              return (
                <Card
                  key={agent.name}
                  variant="glass"
                  className={`group hover:shadow-lg transition-all duration-300 border ${colors.border}`}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div className={`h-10 w-10 rounded-xl ${colors.bg} flex items-center justify-center`}>
                        <Icon className={`h-5 w-5 ${colors.text}`} />
                      </div>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => triggerAgent(agent.name)}
                        disabled={isRunning}
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        {isRunning ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Play className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                    <h3 className="font-semibold text-sm mb-1">
                      {agent.name.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                    </h3>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={agent.status === "running" ? "success" : "secondary"}
                        className="text-2xs"
                      >
                        {agent.status}
                      </Badge>
                      {agent.hypotheses_generated > 0 && (
                        <span className="text-2xs text-muted-foreground">
                          {agent.hypotheses_generated} ideas
                        </span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </TabsContent>

        {/* Queue Tab */}
        <TabsContent value="queue" className="mt-6">
          <Card variant="elevated">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Lightbulb className="h-5 w-5 text-amber-500" />
                Hypothesis Queue
                <Badge variant="secondary" className="ml-2">{stats?.queue_size || 0} pending</Badge>
              </CardTitle>
              <CardDescription>Top hypotheses by priority score</CardDescription>
            </CardHeader>
            <CardContent>
              {hypotheses.length === 0 ? (
                <div className="py-12 text-center text-muted-foreground">
                  <Lightbulb className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>No hypotheses in queue. Run an agent to generate ideas.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {hypotheses.map((h) => (
                    <div
                      key={h.id}
                      className="p-4 bg-secondary/30 rounded-xl border border-border/50 hover:bg-secondary/50 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2 flex-wrap">
                            <Badge variant="outline" className="text-2xs">
                              {h.type.replace(/_/g, " ")}
                            </Badge>
                            <Badge
                              variant={h.source.includes("llm") ? "elite" : "secondary"}
                              className="text-2xs"
                            >
                              {h.source.includes("llm") && <Sparkles className="h-2.5 w-2.5 mr-1" />}
                              {h.source}
                            </Badge>
                          </div>
                          <p className="text-sm leading-relaxed">{h.description}</p>
                        </div>
                        <div className="text-right flex-shrink-0">
                          <p className="text-2xl font-bold text-primary">
                            {(h.priority * 100).toFixed(0)}
                          </p>
                          <p className="text-2xs text-muted-foreground">priority</p>
                        </div>
                      </div>
                      <Progress
                        value={h.priority * 100}
                        variant={h.priority > 0.7 ? "success" : h.priority > 0.4 ? "warning" : "default"}
                        className="mt-3 h-1.5"
                      />
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history" className="mt-6">
          <Card variant="elevated">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <FlaskConical className="h-5 w-5 text-emerald-500" />
                Experiment History
              </CardTitle>
              <CardDescription>All experiments sorted by R² improvement</CardDescription>
            </CardHeader>
            <CardContent>
              {experiments.length === 0 ? (
                <div className="py-12 text-center text-muted-foreground">
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
                        <th className="pb-3 font-medium text-right">R² Improvement</th>
                        <th className="pb-3 font-medium text-right">RMSE Change</th>
                        <th className="pb-3 font-medium text-right">Duration</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/50">
                      {experiments.map((exp, i) => (
                        <tr key={i} className="hover:bg-muted/30 transition-colors">
                          <td className="py-4">
                            <code className="text-xs bg-secondary/50 px-2 py-1 rounded">
                              {exp.hypothesis_id}
                            </code>
                          </td>
                          <td className="py-4">
                            <Badge
                              variant={
                                exp.status === "promoted" ? "success" :
                                exp.status === "completed" ? "default" :
                                exp.status === "failed" ? "destructive" : "secondary"
                              }
                            >
                              {exp.status === "promoted" && <CheckCircle2 className="h-3 w-3 mr-1" />}
                              {exp.status === "failed" && <XCircle className="h-3 w-3 mr-1" />}
                              {exp.status}
                            </Badge>
                          </td>
                          <td className="py-4 text-right">
                            <span className={`font-bold ${exp.r2_improvement > 0 ? "text-emerald-600" : "text-rose-600"}`}>
                              {exp.r2_improvement > 0 ? "+" : ""}{(exp.r2_improvement * 100).toFixed(2)}%
                            </span>
                          </td>
                          <td className="py-4 text-right text-muted-foreground">
                            {exp.rmse_improvement > 0 ? "+" : ""}{exp.rmse_improvement.toFixed(3)}
                          </td>
                          <td className="py-4 text-right text-muted-foreground">
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
        <TabsContent value="controls" className="mt-6">
          <div className="space-y-6">
            {/* System Control Row */}
            <div className="grid md:grid-cols-3 gap-4">
              {/* System Status */}
              <Card variant="elevated" className={continuousStatus?.running ? "border-emerald-500/40 glow-green" : ""}>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`h-10 w-10 rounded-xl ${continuousStatus?.running ? "bg-emerald-500/15" : "bg-secondary"} flex items-center justify-center`}>
                        {continuousStatus?.running ? (
                          <Activity className="h-5 w-5 text-emerald-500 animate-pulse" />
                        ) : (
                          <Square className="h-5 w-5 text-muted-foreground" />
                        )}
                      </div>
                      <div>
                        <p className="font-semibold">ML System</p>
                        <p className="text-xs text-muted-foreground">
                          {continuousStatus?.running ? "Running" : "Stopped"}
                        </p>
                      </div>
                    </div>
                    <Switch
                      checked={continuousStatus?.running || false}
                      onCheckedChange={toggleContinuous}
                      disabled={actionLoading === "continuous"}
                    />
                  </div>
                  {continuousStatus?.running && (
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Strategy</span>
                        <Badge variant="secondary">{continuousStatus.strategy}</Badge>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Uptime</span>
                        <span className="font-mono">{formatUptime(continuousStatus.uptime_seconds)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">PID</span>
                        <code className="text-xs bg-secondary px-2 py-0.5 rounded">{continuousStatus.pid}</code>
                      </div>
                    </div>
                  )}
                  {!continuousStatus?.running && (
                    <div className="space-y-2">
                      <label className="text-xs text-muted-foreground">Strategy when started:</label>
                      <Select value={selectedStrategy} onValueChange={setSelectedStrategy}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="exploration">Exploration</SelectItem>
                          <SelectItem value="exploitation">Exploitation</SelectItem>
                          <SelectItem value="adversarial">Adversarial</SelectItem>
                          <SelectItem value="ensemble">Ensemble</SelectItem>
                          <SelectItem value="data-centric">Data-Centric</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Run Hypothesis */}
              <Card variant="elevated">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="h-10 w-10 rounded-xl bg-purple-500/15 flex items-center justify-center">
                      <Play className="h-5 w-5 text-purple-500" />
                    </div>
                    <div>
                      <p className="font-semibold">Run Hypothesis</p>
                      <p className="text-xs text-muted-foreground">Pick from queue</p>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <Select value={selectedHypothesisId} onValueChange={setSelectedHypothesisId}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select hypothesis..." />
                      </SelectTrigger>
                      <SelectContent>
                        {hypotheses.map((h) => (
                          <SelectItem key={h.id} value={h.id}>
                            <div className="flex items-center gap-2">
                              <Badge variant="outline" className="text-2xs">{h.type.replace(/_/g, " ")}</Badge>
                              <span className="truncate max-w-[150px]">{h.description.slice(0, 30)}...</span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button
                      className="w-full"
                      onClick={runHypothesis}
                      disabled={!selectedHypothesisId || actionLoading === "run-hypothesis"}
                    >
                      {actionLoading === "run-hypothesis" ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <Play className="h-4 w-4 mr-2" />
                      )}
                      Run Selected
                    </Button>
                  </div>
                </CardContent>
              </Card>

              {/* Create Hypothesis */}
              <Card variant="elevated" className="border-amber-500/40">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-amber-500 to-yellow-400 flex items-center justify-center shadow-lg shadow-amber-500/25">
                      <Sparkles className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <p className="font-semibold">New Hypothesis</p>
                      <p className="text-xs text-muted-foreground">Create custom experiment</p>
                    </div>
                  </div>
                  <Button
                    variant="premium"
                    className="w-full"
                    onClick={() => setShowHypothesisBuilder(true)}
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Create Hypothesis
                  </Button>
                  <p className="text-2xs text-muted-foreground mt-3 text-center">
                    Configure features, architecture, hyperparameters
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* Quick Cycle Buttons */}
            <Card variant="elevated">
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-lg bg-amber-500/15 flex items-center justify-center">
                    <Zap className="h-4 w-4 text-amber-500" />
                  </div>
                  <div>
                    <CardTitle className="text-lg">Quick Improvement Cycles</CardTitle>
                    <CardDescription>Run a single cycle with a specific strategy</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                  {[
                    { name: "exploration", desc: "Explore new ideas", icon: Lightbulb, color: "purple" },
                    { name: "exploitation", desc: "Refine winners", icon: Target, color: "emerald" },
                    { name: "adversarial", desc: "Fix failures", icon: AlertTriangle, color: "rose" },
                    { name: "ensemble", desc: "Optimize blend", icon: Layers, color: "sky" },
                    { name: "data-centric", desc: "Improve data", icon: Database, color: "amber" },
                  ].map(({ name, desc, icon: StrategyIcon, color }) => {
                    const isRunning = actionLoading === `cycle-${name}`;
                    const colorClasses: Record<string, string> = {
                      purple: "hover:border-purple-500/40 hover:bg-purple-500/5",
                      emerald: "hover:border-emerald-500/40 hover:bg-emerald-500/5",
                      rose: "hover:border-rose-500/40 hover:bg-rose-500/5",
                      sky: "hover:border-sky-500/40 hover:bg-sky-500/5",
                      amber: "hover:border-amber-500/40 hover:bg-amber-500/5",
                    };
                    return (
                      <Button
                        key={name}
                        variant="outline"
                        className={`h-auto py-3 flex-col ${colorClasses[color]}`}
                        onClick={() => triggerCycle(name)}
                        disabled={isRunning}
                      >
                        {isRunning ? (
                          <Loader2 className="h-5 w-5 mb-1 animate-spin" />
                        ) : (
                          <StrategyIcon className="h-5 w-5 mb-1" />
                        )}
                        <span className="font-medium text-xs">{name.charAt(0).toUpperCase() + name.slice(1)}</span>
                        <span className="text-2xs text-muted-foreground">{desc}</span>
                      </Button>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            {/* LLM Status */}
            <Card variant="elevated">
              <CardHeader className="pb-2">
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-lg bg-pink-500/15 flex items-center justify-center">
                    <Sparkles className="h-4 w-4 text-pink-500" />
                  </div>
                  <div>
                    <CardTitle className="text-lg">Local LLM Connection</CardTitle>
                    <CardDescription>Creative reasoning at $0 cost</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-6">
                  <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${
                    llmStatus?.connected
                      ? "bg-emerald-500/10 border-emerald-500/30"
                      : "bg-rose-500/10 border-rose-500/30"
                  }`}>
                    <div className={`h-4 w-4 rounded-full ${llmStatus?.connected ? "bg-emerald-500 animate-pulse" : "bg-rose-500"}`} />
                    <span className="font-medium">
                      {llmStatus?.connected ? "Connected" : "Disconnected"}
                    </span>
                    {llmStatus?.cost && (
                      <Badge variant="success">{llmStatus.cost}</Badge>
                    )}
                  </div>
                  {llmStatus?.url && (
                    <div className="flex-1 flex items-center gap-4 text-sm">
                      <div>
                        <span className="text-muted-foreground">Endpoint:</span>{" "}
                        <code className="text-xs bg-secondary px-2 py-1 rounded">{llmStatus.url}</code>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Model:</span>{" "}
                        <code className="text-xs bg-secondary px-2 py-1 rounded">{llmStatus.model}</code>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
      )}

      {/* Footer */}
      {data?.last_updated && (
        <p className="text-xs text-muted-foreground text-center pt-4 border-t border-border/50">
          Last updated: {new Date(data.last_updated).toLocaleString()}
        </p>
      )}

      {/* Hypothesis Builder Modal */}
      <HypothesisBuilder
        open={showHypothesisBuilder}
        onClose={() => setShowHypothesisBuilder(false)}
        onSubmit={submitHypothesis}
        apiBase={API_BASE}
      />
    </div>
  );
}
