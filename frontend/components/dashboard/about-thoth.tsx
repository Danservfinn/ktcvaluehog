"use client";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Layers,
  Database,
  Brain,
  TrendingUp,
  ArrowLeftRight,
  Bot,
  Rocket,
  Sparkles,
  CheckCircle2,
  LucideIcon,
} from "lucide-react";

interface Section {
  id: string;
  title: string;
  subtitle?: string;
  icon: LucideIcon;
  badge?: "elite";
  content: React.ReactNode;
}

// Data sources table
const dataSources = [
  { source: "Player Stats", nodes: "143K+", description: "Weekly game logs (2000-2024)" },
  { source: "Snap Counts", nodes: "249K", description: "Play participation data" },
  { source: "Next Gen Stats", nodes: "24K", description: "Advanced NFL tracking" },
  { source: "KTC Valuations", nodes: "52K", description: "Dynasty trade values" },
  { source: "Injuries", nodes: "49K", description: "Injury history & profiles" },
  { source: "Combine", nodes: "7K", description: "Athletic testing results" },
  { source: "Weather/Betting", nodes: "29K", description: "Game conditions & Elo" },
];

// ML component models
const mlComponents = [
  { model: "LightGBM", r2: "0.803", description: "Primary gradient boosting" },
  { model: "Random Forest", r2: "0.765", description: "Ensemble stability" },
  { model: "Ridge Regression", r2: "0.707", description: "Linear baseline" },
  { model: "Feature Attention NN", r2: "0.695", description: "Complex patterns" },
];

// Getting started steps
const gettingStartedSteps = [
  "Search any player to see their profile",
  "Connect your Sleeper league for personalized insights",
  "Use Trade Analyzer to evaluate deals",
  "Check Market Movers for buy/sell opportunities",
  "Upgrade to Elite for ML-powered projections",
];

// Section definitions following Miller's Law (7 sections)
const sections: Section[] = [
  {
    id: "overview",
    title: "Platform Overview",
    icon: Layers,
    content: (
      <div className="space-y-4">
        <p className="text-muted-foreground leading-relaxed">
          Thoth combines a <span className="text-foreground font-medium">Neo4j graph database</span> with
          over 750,000 nodes and cutting-edge <span className="text-foreground font-medium">machine learning</span> to
          deliver dynasty fantasy football insights that go beyond surface-level analysis.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
            <span className="text-sm">Graph relationships connect player performance to injuries, depth charts, and game conditions</span>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
            <span className="text-sm">Named after the Egyptian god of wisdom - synthesizing vast data into actionable insights</span>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
            <span className="text-sm">Era-normalized features spanning 25 years of NFL data (1999-2024)</span>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
            <span className="text-sm">Daily model retraining keeps predictions current and accurate</span>
          </div>
        </div>
      </div>
    ),
  },
  {
    id: "data",
    title: "Data Sources",
    subtitle: "750K+ Nodes",
    icon: Database,
    content: (
      <div className="space-y-4">
        <p className="text-muted-foreground text-sm">
          Our graph database connects disparate data sources into meaningful relationships,
          revealing insights impossible to find in traditional databases.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 font-medium">Source</th>
                <th className="text-right py-2 font-medium">Nodes</th>
                <th className="text-left py-2 pl-4 font-medium hidden sm:table-cell">Description</th>
              </tr>
            </thead>
            <tbody>
              {dataSources.map((row) => (
                <tr key={row.source} className="border-b border-border/50">
                  <td className="py-2 text-foreground">{row.source}</td>
                  <td className="py-2 text-right">
                    <Badge variant="secondary" className="font-mono text-xs">
                      {row.nodes}
                    </Badge>
                  </td>
                  <td className="py-2 pl-4 text-muted-foreground hidden sm:table-cell">
                    {row.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    ),
  },
  {
    id: "ml",
    title: "ML Prediction Engine",
    subtitle: "R² = 0.80",
    icon: Brain,
    content: (
      <div className="space-y-4">
        <div className="p-4 rounded-lg bg-gradient-to-br from-amber-500/10 via-yellow-500/5 to-amber-500/10 border border-amber-500/20">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="h-4 w-4 text-amber-500" />
            <span className="font-semibold text-amber-700">Stacked Ensemble Architecture</span>
          </div>
          <p className="text-sm text-muted-foreground">
            Our R² = 0.80 means the model explains <span className="text-foreground font-medium">80% of the variance</span> in
            fantasy points per game - among the most accurate publicly available dynasty projections.
          </p>
        </div>

        <div>
          <h4 className="font-medium mb-2">4 Component Models</h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {mlComponents.map((model) => (
              <div key={model.model} className="flex items-center justify-between p-2 rounded-lg bg-secondary/50">
                <div>
                  <span className="text-sm font-medium">{model.model}</span>
                  <p className="text-xs text-muted-foreground">{model.description}</p>
                </div>
                <Badge variant="outline" className="font-mono text-xs">
                  R²={model.r2}
                </Badge>
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
            <span>177 era-normalized features</span>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
            <span>Daily retraining via GitHub Actions</span>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
            <span>Position-specific models (QB/RB/WR/TE)</span>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
            <span>10,596 training samples (1999-2023)</span>
          </div>
        </div>
      </div>
    ),
  },
  {
    id: "dynasty",
    title: "Dynasty Intelligence",
    icon: TrendingUp,
    content: (
      <div className="space-y-4">
        <p className="text-muted-foreground text-sm">
          Go beyond raw values with intelligent signals that identify market inefficiencies
          and help you make smarter dynasty decisions.
        </p>
        <div className="space-y-3">
          <div className="p-3 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-2 mb-1">
              <Badge className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20">Edge Signals</Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              Our algorithm identifies undervalued players. Positive edge = buy opportunity.
            </p>
          </div>
          <div className="p-3 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-2 mb-1">
              <Badge className="bg-sky-500/10 text-sky-600 border-sky-500/20">Value Trends</Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              7-day momentum tracking shows market direction before consensus catches on.
            </p>
          </div>
          <div className="p-3 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="elite">Elite</Badge>
              <span className="text-sm font-medium">Dynasty Health Score</span>
            </div>
            <p className="text-sm text-muted-foreground">
              Long-term roster sustainability metric combining age curves, contract situations, and depth.
            </p>
          </div>
          <div className="p-3 rounded-lg border border-border bg-card">
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="elite">Elite</Badge>
              <span className="text-sm font-medium">Championship Odds</span>
            </div>
            <p className="text-sm text-muted-foreground">
              Monte Carlo simulation calculates your title probability based on roster strength.
            </p>
          </div>
        </div>
      </div>
    ),
  },
  {
    id: "trade",
    title: "Trade Analysis",
    icon: ArrowLeftRight,
    content: (
      <div className="space-y-4">
        <p className="text-muted-foreground text-sm">
          Make confident trade decisions with comprehensive analysis that goes beyond simple value calculators.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div className="p-3 rounded-lg border border-border bg-card">
            <h4 className="font-medium text-sm mb-1">KTC Value Comparison</h4>
            <p className="text-xs text-muted-foreground">Market-based trade fairness from KeepTradeCut crowd-sourced values</p>
          </div>
          <div className="p-3 rounded-lg border border-border bg-card">
            <h4 className="font-medium text-sm mb-1">ML Projection Overlay</h4>
            <p className="text-xs text-muted-foreground">Future value vs current price reveals hidden value (Elite)</p>
          </div>
          <div className="p-3 rounded-lg border border-border bg-card">
            <h4 className="font-medium text-sm mb-1">Risk Assessment</h4>
            <p className="text-xs text-muted-foreground">Injury history, age curves, and situation changes factored in</p>
          </div>
          <div className="p-3 rounded-lg border border-border bg-card">
            <h4 className="font-medium text-sm mb-1">Written Analysis</h4>
            <p className="text-xs text-muted-foreground">Detailed explanation of trade dynamics and recommendations</p>
          </div>
        </div>
        <div className="flex items-start gap-2 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
          <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
          <span className="text-sm">Find trades that look fair but favor you long-term using ML projections</span>
        </div>
      </div>
    ),
  },
  {
    id: "ai",
    title: "Thoth AI Assistant",
    icon: Bot,
    badge: "elite",
    content: (
      <div className="space-y-4">
        <div className="p-4 rounded-lg bg-gradient-to-br from-amber-500/10 via-yellow-500/5 to-amber-500/10 border border-amber-500/20">
          <div className="flex items-center gap-2 mb-2">
            <Bot className="h-4 w-4 text-amber-500" />
            <span className="font-semibold text-amber-700">Powered by Claude AI</span>
          </div>
          <p className="text-sm text-muted-foreground">
            Ask complex dynasty questions in natural language and receive analysis that considers
            your specific roster, league settings, and goals.
          </p>
        </div>

        <div className="space-y-2">
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
            <div>
              <span className="text-sm font-medium">BYOK (Bring Your Own Key)</span>
              <p className="text-xs text-muted-foreground">Your Anthropic API key stays private - never stored on our servers</p>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
            <div>
              <span className="text-sm font-medium">Dynasty Context</span>
              <p className="text-xs text-muted-foreground">AI has access to all 750K+ data points for informed responses</p>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
            <div>
              <span className="text-sm font-medium">Trade Advice</span>
              <p className="text-xs text-muted-foreground">Get personalized recommendations for incoming trade offers</p>
            </div>
          </div>
          <div className="flex items-start gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
            <div>
              <span className="text-sm font-medium">Player Research</span>
              <p className="text-xs text-muted-foreground">Deep analysis on any player combining stats, trends, and projections</p>
            </div>
          </div>
        </div>
      </div>
    ),
  },
  {
    id: "start",
    title: "Getting Started",
    icon: Rocket,
    content: (
      <div className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="p-3 rounded-lg border border-border bg-card text-center">
            <h4 className="font-medium text-sm">Free</h4>
            <p className="text-2xl font-bold text-primary">$0</p>
            <p className="text-xs text-muted-foreground mt-1">Top 100 rankings, 3 trades/day</p>
          </div>
          <div className="p-3 rounded-lg border border-border bg-card text-center">
            <h4 className="font-medium text-sm">Pro</h4>
            <p className="text-2xl font-bold text-primary">$9.99<span className="text-xs font-normal text-muted-foreground">/mo</span></p>
            <p className="text-xs text-muted-foreground mt-1">Extended rankings, unlimited trades</p>
          </div>
          <div className="p-3 rounded-lg border border-amber-500/30 bg-gradient-to-br from-amber-500/10 to-yellow-500/5 text-center">
            <h4 className="font-medium text-sm flex items-center justify-center gap-1">
              <Sparkles className="h-3 w-3 text-amber-500" />
              Elite
            </h4>
            <p className="text-2xl font-bold text-amber-600">$19.99<span className="text-xs font-normal text-muted-foreground">/mo</span></p>
            <p className="text-xs text-muted-foreground mt-1">ML projections, Thoth AI, league analysis</p>
          </div>
        </div>

        <div>
          <h4 className="font-medium mb-2">Quick Start</h4>
          <div className="space-y-2">
            {gettingStartedSteps.map((step, i) => (
              <div key={i} className="flex items-center gap-3">
                <div className="h-6 w-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-medium shrink-0">
                  {i + 1}
                </div>
                <span className="text-sm">{step}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    ),
  },
];

export function AboutThoth() {
  return (
    <Card variant="glass" className="overflow-hidden">
      <CardHeader className="border-b border-border/50">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/25">
            <Sparkles className="h-5 w-5 text-black" />
          </div>
          <div>
            <CardTitle>About Thoth</CardTitle>
            <p className="text-sm text-muted-foreground">
              Named after the Egyptian god of wisdom and knowledge
            </p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <Accordion type="single" collapsible className="w-full">
          {sections.map((section) => {
            const Icon = section.icon;
            return (
              <AccordionItem key={section.id} value={section.id} className="border-border/50">
                <AccordionTrigger className="px-6 hover:bg-secondary/50 hover:no-underline">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center">
                      <Icon className="h-4 w-4 text-primary" />
                    </div>
                    <span className="font-medium">{section.title}</span>
                    {section.subtitle && (
                      <Badge variant="secondary" className="font-mono text-xs">
                        {section.subtitle}
                      </Badge>
                    )}
                    {section.badge === "elite" && (
                      <Badge variant="elite">
                        <Sparkles className="h-3 w-3 mr-1" />
                        Elite
                      </Badge>
                    )}
                  </div>
                </AccordionTrigger>
                <AccordionContent className="px-6 pb-6">
                  {section.content}
                </AccordionContent>
              </AccordionItem>
            );
          })}
        </Accordion>
      </CardContent>
    </Card>
  );
}
