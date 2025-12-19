"use client";

import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  FileText,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Loader2,
  Wand2,
  AlertCircle,
  Copy,
  Check,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { TradeNarrative, EliteTradeAnalysis, api } from "@/lib/api";
import { getAnthropicKey } from "@/lib/byok";

interface WrittenReportSectionProps {
  narrative: TradeNarrative;
  analysis: EliteTradeAnalysis;
  givePlayers: string[];
  getPlayers: string[];
}

function ReportSection({
  title,
  content,
  defaultOpen = true,
}: {
  title: string;
  content: string | string[];
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  const contentArray = Array.isArray(content) ? content : [content];

  return (
    <div className="border-b border-border/50 last:border-0">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between py-3 px-1 text-left hover:bg-secondary/30 transition-colors"
      >
        <h3 className="font-semibold text-base">{title}</h3>
        {isOpen ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </button>
      {isOpen && (
        <div className="pb-4 px-1 space-y-3">
          {contentArray.map((paragraph, idx) => (
            <p key={idx} className="research-paper-text">
              {paragraph}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

function PlayerAnalysisSection({
  title,
  paragraphs,
  playerNames,
}: {
  title: string;
  paragraphs: string[];
  playerNames: string[];
}) {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <div className="border-b border-border/50">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between py-3 px-1 text-left hover:bg-secondary/30 transition-colors"
      >
        <h3 className="font-semibold text-base">{title}</h3>
        {isOpen ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </button>
      {isOpen && (
        <div className="pb-4 px-1 space-y-4">
          {paragraphs.map((paragraph, idx) => (
            <div key={idx}>
              {playerNames[idx] && (
                <h4 className="font-medium text-sm text-primary mb-2">
                  {playerNames[idx]}
                </h4>
              )}
              <p className="research-paper-text">{paragraph}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function WrittenReportSection({
  narrative,
  analysis,
  givePlayers,
  getPlayers,
}: WrittenReportSectionProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [isEnhancing, setIsEnhancing] = useState(false);
  const [enhancedNarrative, setEnhancedNarrative] = useState<string | null>(null);
  const [enhanceError, setEnhanceError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [hasApiKey, setHasApiKey] = useState(false);
  const enhancedRef = useRef<HTMLDivElement>(null);

  // Check for API key on mount and when window regains focus
  useEffect(() => {
    const checkApiKey = () => setHasApiKey(!!getAnthropicKey());
    checkApiKey();

    window.addEventListener("focus", checkApiKey);
    window.addEventListener("storage", checkApiKey);

    return () => {
      window.removeEventListener("focus", checkApiKey);
      window.removeEventListener("storage", checkApiKey);
    };
  }, []);

  // Get player names for the analysis sections
  const givePlayerNames = analysis.give_side.players.map((p) => p.name);
  const getPlayerNames = analysis.get_side.players.map((p) => p.name);

  const handleEnhance = async () => {
    // Re-check API key directly from localStorage
    const apiKey = getAnthropicKey();
    if (!apiKey) {
      setHasApiKey(false);
      setEnhanceError("Add your Anthropic API key in Settings to use AI enhancement.");
      return;
    }
    setHasApiKey(true);

    setIsEnhancing(true);
    setEnhanceError(null);
    setEnhancedNarrative("");

    try {
      const response = await api.enhanceTradeNarrative(analysis);

      if (!response.ok) {
        const error = await response.text();
        throw new Error(error || "Failed to enhance narrative");
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") continue;

            try {
              const parsed = JSON.parse(data);
              if (parsed.error) {
                throw new Error(parsed.error);
              }
              if (parsed.text) {
                setEnhancedNarrative((prev) => (prev || "") + parsed.text);
              }
            } catch {
              // Skip parse errors
            }
          }
        }
      }
    } catch (err: any) {
      setEnhanceError(err.message || "Failed to enhance narrative");
    } finally {
      setIsEnhancing(false);
    }
  };

  const handleCopy = () => {
    const textToCopy = enhancedNarrative || formatNarrativeForCopy(narrative);
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatNarrativeForCopy = (n: TradeNarrative) => {
    return `# Trade Analysis Report

## Introduction
${n.introduction}

## Players You're Trading Away
${n.player_analysis_give.map((p, i) => `### ${givePlayerNames[i] || `Player ${i + 1}`}\n${p}`).join("\n\n")}

## Players You're Receiving
${n.player_analysis_get.map((p, i) => `### ${getPlayerNames[i] || `Player ${i + 1}`}\n${p}`).join("\n\n")}

## Value Analysis
${n.value_analysis}

## Dynasty Outlook
${n.dynasty_outlook}

## Risk Assessment
${n.risk_assessment}

## Recommendation
${n.recommendation}

## Closing
${n.closing}
`;
  };

  // Scroll to enhanced content when it starts
  useEffect(() => {
    if (enhancedNarrative && enhancedRef.current) {
      enhancedRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [enhancedNarrative?.length === 1]);

  return (
    <Card className="research-paper">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary" />
            <CardTitle className="text-lg">Written Analysis Report</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCopy}
              className="h-8 px-2"
            >
              {copied ? (
                <Check className="h-4 w-4 text-emerald-500" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
              className="h-8 px-2"
            >
              {isExpanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </CardHeader>

      {isExpanded && (
        <CardContent className="pt-0">
          {/* AI Enhancement Section */}
          {!enhancedNarrative && (
            <div className="mb-6 p-4 bg-gradient-to-r from-amber-500/10 to-purple-500/10 border border-amber-500/20 rounded-lg">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className="h-4 w-4 text-amber-500" />
                    <span className="font-medium text-sm">Enhance with AI</span>
                    <Badge variant="outline" className="text-xs">
                      Claude Opus 4.5
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Generate a richer, more dynamic analysis using Claude Opus 4.5.
                    {!hasApiKey && " Requires your Anthropic API key."}
                  </p>
                </div>
                <Button
                  variant="premium"
                  size="sm"
                  onClick={handleEnhance}
                  disabled={isEnhancing}
                  className="shrink-0"
                >
                  {isEnhancing ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Enhancing...
                    </>
                  ) : (
                    <>
                      <Wand2 className="h-4 w-4 mr-2" />
                      Enhance
                    </>
                  )}
                </Button>
              </div>
              {enhanceError && (
                <div className="mt-3 flex items-center gap-2 text-sm text-rose-500">
                  <AlertCircle className="h-4 w-4" />
                  {enhanceError}
                </div>
              )}
            </div>
          )}

          {/* Enhanced Narrative (AI-generated) */}
          {enhancedNarrative && (
            <div ref={enhancedRef} className="mb-6">
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="h-4 w-4 text-amber-500" />
                <span className="font-medium text-sm">AI-Enhanced Analysis</span>
                <Badge className="bg-gradient-to-r from-amber-500 to-purple-500 text-white text-xs">
                  Claude Opus 4.5
                </Badge>
              </div>
              <div className="prose prose-sm prose-slate dark:prose-invert max-w-none prose-headings:font-semibold prose-h1:text-xl prose-h2:text-lg prose-h3:text-base prose-table:text-sm prose-td:px-2 prose-th:px-2">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {enhancedNarrative}
                </ReactMarkdown>
                {isEnhancing && (
                  <span className="inline-block w-2 h-4 bg-primary animate-pulse ml-0.5" />
                )}
              </div>
            </div>
          )}

          {/* Template Narrative (always shown if no enhanced) */}
          {!enhancedNarrative && (
            <div className="space-y-0">
              <ReportSection title="Introduction" content={narrative.introduction} />

              <PlayerAnalysisSection
                title="Players You're Trading Away"
                paragraphs={narrative.player_analysis_give}
                playerNames={givePlayerNames}
              />

              <PlayerAnalysisSection
                title="Players You're Receiving"
                paragraphs={narrative.player_analysis_get}
                playerNames={getPlayerNames}
              />

              <ReportSection title="Value Analysis" content={narrative.value_analysis} />

              <ReportSection title="Dynasty Outlook" content={narrative.dynasty_outlook} />

              <ReportSection title="Risk Assessment" content={narrative.risk_assessment} />

              <ReportSection title="Recommendation" content={narrative.recommendation} />

              <ReportSection
                title="Closing Thoughts"
                content={narrative.closing}
                defaultOpen={true}
              />
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
