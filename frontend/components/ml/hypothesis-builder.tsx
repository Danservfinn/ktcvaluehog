"use client";

import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";
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
  FlaskConical,
  Target,
  Layers,
  Database,
  Sparkles,
  Search,
  ChevronRight,
  ChevronLeft,
  Check,
  Loader2,
  Zap,
  AlertTriangle,
  Code,
  GitBranch,
  MessageSquare,
  ClipboardList,
  Lightbulb,
  Cpu,
  ArrowRight,
} from "lucide-react";
import { useLocalStorage } from "@/hooks/use-local-storage";

interface FeatureInfo {
  name: string;
  category: string;
  category_label: string;
  description: string;
  correlation: number | null;
}

interface FeatureCategory {
  category: string;
  label: string;
  description: string;
  count: number;
  features: FeatureInfo[];
}

interface HypothesisType {
  value: string;
  label: string;
  description: string;
}

// NLP Parsing types
interface MatchedFeature {
  name: string;
  category: string;
  description: string;
  correlation: number | null;
  match_confidence: number;
  match_reason: string;
}

interface ParsedHypothesis {
  success: boolean;
  hypothesis_type: string;
  hypothesis_type_confidence: number;
  matched_features: MatchedFeature[];
  suggested_operation: string | null;
  suggested_formula: string | null;
  generated_description: string;
  expected_impact: string | null;
  warnings: string[];
  alternative_interpretations: string[];
  llm_source: "anthropic" | "local";
}

interface LLMStatus {
  connected: boolean;
  url: string;
  model: string | null;
}

interface HypothesisBuilderProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (hypothesis: {
    type: string;
    description: string;
    priority: number;
    config: Record<string, unknown>;
    tags: string[];
  }) => Promise<void>;
  apiBase: string;
}

// Type icons mapping
const typeIcons: Record<string, typeof Brain> = {
  feature_addition: FlaskConical,
  feature_removal: AlertTriangle,
  feature_combination: Layers,
  hyperparameter: Zap,
  architecture: Brain,
  ensemble_config: GitBranch,
  data_augmentation: Database,
  loss_function: Target,
  regularization: Sparkles,
  attention_mechanism: Brain,
  position_specialist: Target,
  error_targeted: AlertTriangle,
};

// Type colors
const typeColors: Record<string, string> = {
  feature_addition: "from-emerald-500 to-green-500",
  feature_removal: "from-rose-500 to-red-500",
  feature_combination: "from-purple-500 to-violet-500",
  hyperparameter: "from-amber-500 to-yellow-500",
  architecture: "from-blue-500 to-cyan-500",
  ensemble_config: "from-indigo-500 to-purple-500",
  data_augmentation: "from-sky-500 to-blue-500",
  loss_function: "from-orange-500 to-amber-500",
  regularization: "from-pink-500 to-rose-500",
  attention_mechanism: "from-violet-500 to-purple-500",
  position_specialist: "from-teal-500 to-cyan-500",
  error_targeted: "from-red-500 to-orange-500",
};

export function HypothesisBuilder({
  open,
  onClose,
  onSubmit,
  apiBase,
}: HypothesisBuilderProps) {
  // Step 0 = mode selection, then 1-4 for wizard steps
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  // Mode selection: "guided" or "natural"
  const [inputMode, setInputMode] = useState<"guided" | "natural">("guided");

  // NLP state
  const [nlpInput, setNlpInput] = useState("");
  const [isParsing, setIsParsing] = useState(false);
  const [parsedResult, setParsedResult] = useState<ParsedHypothesis | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);
  const [useLocalLlm, setUseLocalLlm] = useState(false);
  const [llmStatus, setLlmStatus] = useState<LLMStatus | null>(null);

  // Get API key from localStorage (BYOK pattern)
  const [anthropicKey] = useLocalStorage<string | null>("anthropic_api_key", null);

  // Form state
  const [selectedType, setSelectedType] = useState<string>("");
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);
  const [featureOperation, setFeatureOperation] = useState<"add" | "combine" | "remove">("add");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState([5]);
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState("");

  // Data from API
  const [hypothesisTypes, setHypothesisTypes] = useState<HypothesisType[]>([]);
  const [featureCategories, setFeatureCategories] = useState<FeatureCategory[]>([]);
  const [featureSearch, setFeatureSearch] = useState("");
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  // Fetch data on mount
  useEffect(() => {
    if (open) {
      fetchData();
    }
  }, [open]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [typesRes, featuresRes, llmRes] = await Promise.all([
        fetch(`${apiBase}/api/v1/ml-monitor/hypothesis-types`),
        fetch(`${apiBase}/api/v1/ml-monitor/features/categories`),
        fetch(`${apiBase}/api/v1/ml-monitor/llm`),
      ]);

      if (typesRes.ok) {
        const data = await typesRes.json();
        setHypothesisTypes(data.types || []);
      }

      if (featuresRes.ok) {
        const data = await featuresRes.json();
        setFeatureCategories(data.categories || []);
        // Expand first two categories by default
        if (data.categories?.length > 0) {
          setExpandedCategories(new Set(data.categories.slice(0, 2).map((c: FeatureCategory) => c.category)));
        }
      }

      if (llmRes.ok) {
        const data = await llmRes.json();
        setLlmStatus(data);
        // Default to local LLM if available and no Anthropic key
        if (data.connected && !anthropicKey) {
          setUseLocalLlm(true);
        }
      }
    } catch (error) {
      console.error("Failed to fetch hypothesis builder data:", error);
    } finally {
      setLoading(false);
    }
  };

  // Parse natural language hypothesis
  const parseNaturalLanguage = async () => {
    if (!nlpInput.trim() || nlpInput.length < 10) return;

    setIsParsing(true);
    setParseError(null);

    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };

      // Add Anthropic key if using BYOK (not local LLM)
      if (!useLocalLlm && anthropicKey) {
        headers["X-Anthropic-Key"] = anthropicKey;
      }

      const response = await fetch(`${apiBase}/api/v1/ml-monitor/hypothesis/parse-description`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          description: nlpInput,
          use_local_llm: useLocalLlm,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to parse hypothesis");
      }

      const result: ParsedHypothesis = await response.json();
      setParsedResult(result);

      // Pre-fill form state from parsed result
      setSelectedType(result.hypothesis_type);
      setDescription(result.generated_description);
      setSelectedFeatures(result.matched_features.map((f) => f.name));

      // Determine feature operation from parsed result
      if (result.suggested_operation === "interaction" || result.suggested_operation === "ratio") {
        setFeatureOperation("combine");
      } else if (result.hypothesis_type === "feature_removal") {
        setFeatureOperation("remove");
      } else {
        setFeatureOperation("add");
      }

      // Move to analysis view
      setStep(2);
    } catch (error) {
      console.error("Parse error:", error);
      setParseError(error instanceof Error ? error.message : "Unknown error occurred");
    } finally {
      setIsParsing(false);
    }
  };

  const resetForm = () => {
    setStep(0);
    setInputMode("guided");
    setNlpInput("");
    setParsedResult(null);
    setParseError(null);
    setSelectedType("");
    setSelectedFeatures([]);
    setFeatureOperation("add");
    setDescription("");
    setPriority([5]);
    setTags([]);
    setTagInput("");
    setFeatureSearch("");
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const config: Record<string, unknown> = {};

      // Build config based on type
      if (selectedType.includes("feature")) {
        config.feature_names = selectedFeatures;
        config.operation = featureOperation;
        if (featureOperation === "combine" && selectedFeatures.length >= 2) {
          config.formula = `df['${selectedFeatures[0]}'] * df['${selectedFeatures[1]}']`;
          config.new_feature_name = selectedFeatures.join("_x_");
        }
      }

      await onSubmit({
        type: selectedType,
        description,
        priority: priority[0],
        config,
        tags,
      });

      handleClose();
    } catch (error) {
      console.error("Failed to submit hypothesis:", error);
    } finally {
      setSubmitting(false);
    }
  };

  const toggleCategory = (category: string) => {
    const next = new Set(expandedCategories);
    if (next.has(category)) {
      next.delete(category);
    } else {
      next.add(category);
    }
    setExpandedCategories(next);
  };

  const toggleFeature = (featureName: string) => {
    setSelectedFeatures((prev) =>
      prev.includes(featureName)
        ? prev.filter((f) => f !== featureName)
        : [...prev, featureName]
    );
  };

  const addTag = () => {
    if (tagInput.trim() && !tags.includes(tagInput.trim())) {
      setTags([...tags, tagInput.trim()]);
      setTagInput("");
    }
  };

  const removeTag = (tag: string) => {
    setTags(tags.filter((t) => t !== tag));
  };

  // Filter features by search
  const filteredCategories = featureCategories.map((cat) => ({
    ...cat,
    features: cat.features.filter(
      (f) =>
        f.name.toLowerCase().includes(featureSearch.toLowerCase()) ||
        f.description.toLowerCase().includes(featureSearch.toLowerCase())
    ),
  })).filter((cat) => cat.features.length > 0);

  const totalFeatures = featureCategories.reduce((sum, cat) => sum + cat.count, 0);

  // Determine if we should show feature step
  const showFeatureStep = selectedType.includes("feature");

  const canProceed = () => {
    // Step 0: Mode selection - always can proceed
    if (step === 0) return true;

    // Natural language flow
    if (inputMode === "natural") {
      if (step === 1) return nlpInput.length >= 10;
      if (step === 2) return parsedResult !== null;
      if (step === 3) return description.length >= 10;
      return true;
    }

    // Guided flow
    if (step === 1) return !!selectedType;
    if (step === 2) {
      if (showFeatureStep) {
        return selectedFeatures.length > 0;
      }
      return true;
    }
    if (step === 3) return description.length >= 10;
    return true;
  };

  // Calculate step display (skip step 0 in display)
  const displayStep = step === 0 ? 0 : step;
  const totalSteps = inputMode === "natural" ? 4 : 4;

  // Check if LLM is available for NLP mode
  const canUseNlp = llmStatus?.connected || !!anthropicKey;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader className="flex-shrink-0 border-b pb-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-amber-500 to-yellow-400 flex items-center justify-center shadow-lg shadow-amber-500/25">
                <Sparkles className="h-5 w-5 text-white" />
              </div>
              <div>
                <DialogTitle className="text-xl">Create New Hypothesis</DialogTitle>
                <DialogDescription>
                  {step === 0
                    ? "Choose how you want to create your hypothesis"
                    : `Step ${displayStep} of ${totalSteps} - ${inputMode === "natural" ? "AI-Assisted" : "Guided"} mode`}
                </DialogDescription>
              </div>
            </div>
            {step > 0 && (
              <div className="flex items-center gap-1">
                {[1, 2, 3, 4].map((s) => (
                  <div
                    key={s}
                    className={`h-2 w-8 rounded-full transition-colors ${
                      s <= step ? "bg-gradient-to-r from-amber-500 to-yellow-400" : "bg-secondary"
                    }`}
                  />
                ))}
              </div>
            )}
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-6">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : (
            <>
              {/* Step 0: Mode Selection */}
              {step === 0 && (
                <div className="space-y-6">
                  <h3 className="text-lg font-semibold">How would you like to create your hypothesis?</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Natural Language Mode */}
                    <button
                      onClick={() => setInputMode("natural")}
                      disabled={!canUseNlp}
                      className={`relative p-6 rounded-xl border-2 text-left transition-all ${
                        inputMode === "natural"
                          ? "border-amber-500 bg-gradient-to-br from-amber-500/10 to-yellow-500/5 shadow-lg shadow-amber-500/20"
                          : canUseNlp
                            ? "border-border hover:border-primary/40 bg-card"
                            : "border-border bg-secondary/30 opacity-60 cursor-not-allowed"
                      }`}
                    >
                      {inputMode === "natural" && (
                        <div className="absolute top-3 right-3">
                          <Check className="h-5 w-5 text-amber-500" />
                        </div>
                      )}
                      <div className="flex items-center gap-3 mb-3">
                        <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-amber-500 to-yellow-400 flex items-center justify-center shadow-lg">
                          <MessageSquare className="h-6 w-6 text-white" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="font-semibold">AI Natural Language</h4>
                            <Badge variant="premium" className="text-2xs">PREMIUM</Badge>
                          </div>
                        </div>
                      </div>
                      <p className="text-sm text-muted-foreground mb-4">
                        Describe your experiment in plain English. AI will intelligently match your intent
                        to available features and suggest configurations.
                      </p>

                      {/* LLM Source Toggle */}
                      {canUseNlp && (
                        <div className="pt-3 border-t border-border/50">
                          <div className="flex items-center justify-between text-xs">
                            <div className="flex items-center gap-2">
                              <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
                              <span className="text-muted-foreground">AI Engine:</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className={!useLocalLlm ? "font-medium" : "text-muted-foreground"}>
                                Claude
                              </span>
                              <Switch
                                checked={useLocalLlm}
                                onCheckedChange={setUseLocalLlm}
                                disabled={!llmStatus?.connected}
                                className="scale-75"
                              />
                              <span className={useLocalLlm ? "font-medium" : "text-muted-foreground"}>
                                Local
                              </span>
                            </div>
                          </div>
                          <p className="text-2xs text-muted-foreground mt-1">
                            {useLocalLlm
                              ? llmStatus?.model
                                ? `Using: ${llmStatus.model}`
                                : "Local LLM"
                              : anthropicKey
                                ? "Using your Anthropic API key"
                                : "Add API key in Settings"}
                          </p>
                        </div>
                      )}

                      {!canUseNlp && (
                        <div className="pt-3 border-t border-border/50">
                          <p className="text-xs text-amber-600">
                            <AlertTriangle className="h-3 w-3 inline mr-1" />
                            No LLM available. Add Anthropic API key in Settings or connect local LLM.
                          </p>
                        </div>
                      )}
                    </button>

                    {/* Guided Wizard Mode */}
                    <button
                      onClick={() => setInputMode("guided")}
                      className={`relative p-6 rounded-xl border-2 text-left transition-all ${
                        inputMode === "guided"
                          ? "border-primary bg-primary/5 shadow-lg"
                          : "border-border hover:border-primary/40 bg-card"
                      }`}
                    >
                      {inputMode === "guided" && (
                        <div className="absolute top-3 right-3">
                          <Check className="h-5 w-5 text-primary" />
                        </div>
                      )}
                      <div className="flex items-center gap-3 mb-3">
                        <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-primary/80 to-primary flex items-center justify-center shadow-lg">
                          <ClipboardList className="h-6 w-6 text-white" />
                        </div>
                        <h4 className="font-semibold">Guided Wizard</h4>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        Step-by-step selection of hypothesis type, features, and configuration.
                        Browse all 168+ features organized by category.
                      </p>
                    </button>
                  </div>
                </div>
              )}

              {/* Step 1 (NLP): Natural Language Input */}
              {step === 1 && inputMode === "natural" && (
                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold mb-2">Describe Your Hypothesis</h3>
                    <p className="text-sm text-muted-foreground">
                      Tell us what you want to test in plain English. The more detail you provide,
                      the better the AI can match your intent to available features.
                    </p>
                  </div>

                  <Textarea
                    placeholder="Example: I think combining a player's target share with their snap percentage could be a better predictor of dynasty value than either metric alone. Or: Test if adding injury history as a feature improves RB predictions..."
                    value={nlpInput}
                    onChange={(e) => setNlpInput(e.target.value)}
                    className="min-h-[180px] text-base"
                  />
                  <p className="text-xs text-muted-foreground">
                    {nlpInput.length}/2000 characters (minimum 10)
                  </p>

                  {parseError && (
                    <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
                      <div className="flex items-start gap-2">
                        <AlertTriangle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
                        <div>
                          <p className="font-medium text-destructive">Failed to analyze</p>
                          <p className="text-sm text-muted-foreground">{parseError}</p>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="p-4 bg-secondary/50 rounded-lg">
                    <div className="flex items-center gap-2 mb-3">
                      <Lightbulb className="h-4 w-4 text-amber-500" />
                      <span className="font-medium text-sm">Example Prompts</span>
                    </div>
                    <ul className="text-sm text-muted-foreground space-y-2">
                      <li className="flex items-start gap-2">
                        <ArrowRight className="h-3.5 w-3.5 mt-1 text-muted-foreground/50" />
                        <span>"Test if EPA per target correlates better with dynasty value than raw PPG"</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <ArrowRight className="h-3.5 w-3.5 mt-1 text-muted-foreground/50" />
                        <span>"Add a feature that combines injury history with age to predict durability"</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <ArrowRight className="h-3.5 w-3.5 mt-1 text-muted-foreground/50" />
                        <span>"Try increasing the attention heads in the neural network for WR predictions"</span>
                      </li>
                    </ul>
                  </div>

                  <Button
                    onClick={parseNaturalLanguage}
                    disabled={nlpInput.length < 10 || isParsing}
                    className="w-full h-12"
                    variant="premium"
                  >
                    {isParsing ? (
                      <>
                        <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                        Analyzing with AI...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-5 w-5 mr-2" />
                        Analyze with AI
                      </>
                    )}
                  </Button>
                </div>
              )}

              {/* Step 2 (NLP): AI Analysis Results */}
              {step === 2 && inputMode === "natural" && parsedResult && (
                <div className="space-y-6">
                  <div className="flex items-center gap-2">
                    <div className="h-8 w-8 rounded-full bg-emerald-500/15 flex items-center justify-center">
                      <Check className="h-4 w-4 text-emerald-500" />
                    </div>
                    <h3 className="text-lg font-semibold">AI Analysis Complete</h3>
                    <Badge variant="outline" className="text-2xs ml-auto">
                      via {parsedResult.llm_source === "local" ? "Local LLM" : "Claude"}
                    </Badge>
                  </div>

                  {/* Detected Type */}
                  <div className="p-4 bg-secondary/30 rounded-xl">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Detected Type</p>
                        <p className="font-semibold">
                          {hypothesisTypes.find((t) => t.value === parsedResult.hypothesis_type)?.label ||
                            parsedResult.hypothesis_type}
                        </p>
                      </div>
                      <Badge
                        variant={parsedResult.hypothesis_type_confidence > 0.8 ? "success" : "warning"}
                        className="text-xs"
                      >
                        {Math.round(parsedResult.hypothesis_type_confidence * 100)}% confident
                      </Badge>
                    </div>
                  </div>

                  {/* Matched Features */}
                  {parsedResult.matched_features.length > 0 && (
                    <div className="space-y-3">
                      <h4 className="font-medium flex items-center gap-2">
                        <Target className="h-4 w-4 text-primary" />
                        Matched Features ({parsedResult.matched_features.length})
                      </h4>
                      <div className="space-y-2">
                        {parsedResult.matched_features.map((feature, idx) => (
                          <div
                            key={idx}
                            className="p-3 bg-secondary/30 rounded-lg border border-primary/20"
                          >
                            <div className="flex items-start justify-between">
                              <div>
                                <div className="flex items-center gap-2">
                                  <code className="font-mono font-medium text-sm">{feature.name}</code>
                                  <Badge variant="outline" className="text-2xs">
                                    {feature.category.replace("_", " ")}
                                  </Badge>
                                  {feature.correlation !== null && (
                                    <span className="text-2xs text-muted-foreground">
                                      r={feature.correlation.toFixed(2)}
                                    </span>
                                  )}
                                </div>
                                <p className="text-xs text-muted-foreground mt-1">{feature.description}</p>
                              </div>
                              <Badge
                                variant={feature.match_confidence > 0.9 ? "success" : "secondary"}
                                className="text-xs"
                              >
                                {Math.round(feature.match_confidence * 100)}%
                              </Badge>
                            </div>
                            <p className="text-xs text-emerald-600 mt-2 flex items-center gap-1">
                              <Check className="h-3 w-3" />
                              {feature.match_reason}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Suggested Configuration */}
                  {parsedResult.suggested_operation && (
                    <div className="p-4 bg-primary/5 rounded-xl border border-primary/20">
                      <h4 className="font-medium mb-2">Suggested Configuration</h4>
                      <div className="space-y-1 text-sm">
                        <p>
                          <span className="text-muted-foreground">Operation:</span>{" "}
                          <span className="font-mono">{parsedResult.suggested_operation}</span>
                        </p>
                        {parsedResult.suggested_formula && (
                          <p>
                            <span className="text-muted-foreground">Formula:</span>{" "}
                            <code className="bg-secondary px-1 rounded text-xs">
                              {parsedResult.suggested_formula}
                            </code>
                          </p>
                        )}
                        {parsedResult.expected_impact && (
                          <p>
                            <span className="text-muted-foreground">Expected Impact:</span>{" "}
                            <span className="text-emerald-600">{parsedResult.expected_impact}</span>
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Warnings */}
                  {parsedResult.warnings.length > 0 && (
                    <div className="p-4 bg-amber-500/10 rounded-lg border border-amber-500/20">
                      <div className="flex items-start gap-2">
                        <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5" />
                        <div>
                          <p className="font-medium text-amber-700 text-sm">Considerations</p>
                          <ul className="mt-1 space-y-1">
                            {parsedResult.warnings.map((warning, idx) => (
                              <li key={idx} className="text-sm text-muted-foreground">
                                {warning}
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Refined Description */}
                  <div className="p-4 bg-secondary/30 rounded-xl">
                    <p className="text-xs text-muted-foreground mb-2">AI-Refined Description</p>
                    <p className="text-sm leading-relaxed">{parsedResult.generated_description}</p>
                  </div>
                </div>
              )}

              {/* Step 1 (Guided): Select Type */}
              {step === 1 && inputMode === "guided" && (
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">What would you like to improve?</h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {hypothesisTypes.map((type) => {
                      const Icon = typeIcons[type.value] || Brain;
                      const gradient = typeColors[type.value] || "from-gray-500 to-gray-600";
                      const isSelected = selectedType === type.value;

                      return (
                        <button
                          key={type.value}
                          onClick={() => setSelectedType(type.value)}
                          className={`relative p-4 rounded-xl border-2 text-left transition-all hover:scale-[1.02] ${
                            isSelected
                              ? "border-amber-500 bg-amber-500/10 shadow-lg shadow-amber-500/20"
                              : "border-border hover:border-primary/40 bg-card"
                          }`}
                        >
                          {isSelected && (
                            <div className="absolute top-2 right-2">
                              <Check className="h-4 w-4 text-amber-500" />
                            </div>
                          )}
                          <div className={`h-10 w-10 rounded-lg bg-gradient-to-br ${gradient} flex items-center justify-center mb-3`}>
                            <Icon className="h-5 w-5 text-white" />
                          </div>
                          <h4 className="font-semibold text-sm mb-1">{type.label}</h4>
                          <p className="text-xs text-muted-foreground">{type.description}</p>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Step 2 (Guided): Feature Selection (conditional) */}
              {step === 2 && inputMode === "guided" && showFeatureStep && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold">Select Features</h3>
                    <Badge variant="secondary">{totalFeatures} features available</Badge>
                  </div>

                  {/* Operation selector */}
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">Operation:</span>
                    <div className="flex gap-1">
                      {[
                        { value: "add", label: "Add New" },
                        { value: "combine", label: "Combine" },
                        { value: "remove", label: "Remove" },
                      ].map((op) => (
                        <Button
                          key={op.value}
                          variant={featureOperation === op.value ? "default" : "outline"}
                          size="sm"
                          onClick={() => setFeatureOperation(op.value as "add" | "combine" | "remove")}
                        >
                          {op.label}
                        </Button>
                      ))}
                    </div>
                  </div>

                  {/* Search */}
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search features..."
                      value={featureSearch}
                      onChange={(e) => setFeatureSearch(e.target.value)}
                      className="pl-10"
                    />
                  </div>

                  {/* Feature categories */}
                  <div className="border rounded-xl overflow-hidden max-h-[400px] overflow-y-auto">
                    {filteredCategories.map((category) => (
                      <div key={category.category} className="border-b last:border-b-0">
                        <button
                          onClick={() => toggleCategory(category.category)}
                          className="w-full flex items-center justify-between p-3 hover:bg-secondary/50 transition-colors"
                        >
                          <div className="flex items-center gap-2">
                            <ChevronRight
                              className={`h-4 w-4 transition-transform ${
                                expandedCategories.has(category.category) ? "rotate-90" : ""
                              }`}
                            />
                            <span className="font-medium">{category.label}</span>
                            <Badge variant="secondary" className="text-2xs">
                              {category.count}
                            </Badge>
                          </div>
                          <span className="text-xs text-muted-foreground">{category.description}</span>
                        </button>

                        {expandedCategories.has(category.category) && (
                          <div className="p-3 pt-0 grid grid-cols-2 md:grid-cols-3 gap-2">
                            {category.features.map((feature) => {
                              const isSelected = selectedFeatures.includes(feature.name);
                              return (
                                <button
                                  key={feature.name}
                                  onClick={() => toggleFeature(feature.name)}
                                  className={`p-2 rounded-lg text-left text-xs transition-all ${
                                    isSelected
                                      ? "bg-amber-500/15 border-amber-500/40 border"
                                      : "bg-secondary/50 border border-transparent hover:border-primary/20"
                                  }`}
                                >
                                  <div className="flex items-center justify-between mb-1">
                                    <code className="font-mono font-medium">{feature.name}</code>
                                    {feature.correlation !== null && (
                                      <span className={`text-2xs ${feature.correlation > 0.5 ? "text-emerald-500" : "text-muted-foreground"}`}>
                                        r={feature.correlation.toFixed(2)}
                                      </span>
                                    )}
                                  </div>
                                  <p className="text-muted-foreground truncate">{feature.description}</p>
                                </button>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Selected features preview */}
                  {selectedFeatures.length > 0 && (
                    <div className="p-3 bg-secondary/50 rounded-lg">
                      <p className="text-sm font-medium mb-2">Selected: {selectedFeatures.length} features</p>
                      <div className="flex flex-wrap gap-1">
                        {selectedFeatures.map((f) => (
                          <Badge key={f} variant="outline" className="cursor-pointer" onClick={() => toggleFeature(f)}>
                            {f} <span className="ml-1 text-muted-foreground">x</span>
                          </Badge>
                        ))}
                      </div>
                      {featureOperation === "combine" && selectedFeatures.length >= 2 && (
                        <div className="mt-2 p-2 bg-secondary rounded text-xs font-mono">
                          <Code className="h-3 w-3 inline mr-1" />
                          Formula: df['{selectedFeatures[0]}'] * df['{selectedFeatures[1]}']
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Step 3: Details (for both modes) */}
              {((step === 2 && inputMode === "guided" && !showFeatureStep) ||
                (step === 3 && (inputMode === "guided" || inputMode === "natural"))) && (
                <div className="space-y-6">
                  <h3 className="text-lg font-semibold">Hypothesis Details</h3>

                  {/* Description */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Description (what you're testing)</label>
                    <Textarea
                      placeholder="Describe your hypothesis in detail. What improvement do you expect and why?"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      className="min-h-[120px]"
                    />
                    <p className="text-xs text-muted-foreground">
                      {description.length}/500 characters (minimum 10)
                    </p>
                  </div>

                  {/* Priority slider */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium">Priority</label>
                      <span className="text-2xl font-bold text-primary">{priority[0].toFixed(1)}</span>
                    </div>
                    <Slider
                      value={priority}
                      onValueChange={setPriority}
                      min={0}
                      max={10}
                      step={0.5}
                      className="w-full"
                    />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Low Priority</span>
                      <span>High Priority</span>
                    </div>
                  </div>

                  {/* Tags */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Tags</label>
                    <div className="flex gap-2">
                      <Input
                        placeholder="Add a tag..."
                        value={tagInput}
                        onChange={(e) => setTagInput(e.target.value)}
                        onKeyPress={(e) => e.key === "Enter" && addTag()}
                      />
                      <Button variant="outline" onClick={addTag}>Add</Button>
                    </div>
                    {tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {tags.map((tag) => (
                          <Badge
                            key={tag}
                            variant="secondary"
                            className="cursor-pointer"
                            onClick={() => removeTag(tag)}
                          >
                            {tag} <span className="ml-1">x</span>
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Step 4: Review */}
              {step === 4 && (
                <div className="space-y-6">
                  <h3 className="text-lg font-semibold">Review Hypothesis</h3>

                  <div className="bg-secondary/30 rounded-xl p-6 space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Type</p>
                        <p className="font-medium">
                          {hypothesisTypes.find((t) => t.value === selectedType)?.label}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Priority</p>
                        <p className="font-medium">{priority[0].toFixed(1)} / 10</p>
                      </div>
                      {selectedFeatures.length > 0 && (
                        <div className="col-span-2">
                          <p className="text-xs text-muted-foreground mb-1">Features</p>
                          <p className="font-medium">{selectedFeatures.join(", ")}</p>
                        </div>
                      )}
                      {tags.length > 0 && (
                        <div className="col-span-2">
                          <p className="text-xs text-muted-foreground mb-1">Tags</p>
                          <div className="flex flex-wrap gap-1">
                            {tags.map((tag) => (
                              <Badge key={tag} variant="outline">{tag}</Badge>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="pt-4 border-t border-border">
                      <p className="text-xs text-muted-foreground mb-2">Description</p>
                      <p className="text-sm leading-relaxed">{description}</p>
                    </div>

                    {/* Generated config preview */}
                    <div className="pt-4 border-t border-border">
                      <p className="text-xs text-muted-foreground mb-2">Generated Config</p>
                      <pre className="text-xs bg-secondary p-3 rounded-lg overflow-x-auto">
{JSON.stringify({
  type: selectedType,
  priority: priority[0],
  config: selectedFeatures.length > 0 ? {
    feature_names: selectedFeatures,
    operation: featureOperation,
  } : {},
  tags,
}, null, 2)}
                      </pre>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer with navigation */}
        <div className="flex-shrink-0 border-t pt-4 flex items-center justify-between">
          <Button
            variant="ghost"
            onClick={() => {
              if (step === 0) {
                handleClose();
              } else if (step === 1 && inputMode === "natural") {
                // Go back to mode selection
                setStep(0);
                setParsedResult(null);
                setParseError(null);
              } else if (step === 1 && inputMode === "guided") {
                setStep(0);
              } else if (step === 2 && inputMode === "natural") {
                // Go back to NLP input
                setStep(1);
              } else {
                setStep(step - 1);
              }
            }}
          >
            <ChevronLeft className="h-4 w-4 mr-2" />
            {step === 0 ? "Cancel" : "Back"}
          </Button>

          {/* Step 0: Mode selection - show Continue */}
          {step === 0 && (
            <Button
              variant="premium"
              onClick={() => setStep(1)}
              disabled={!canProceed()}
            >
              Continue
              <ChevronRight className="h-4 w-4 ml-2" />
            </Button>
          )}

          {/* Step 1 NLP: Analyze button is in the step, not footer */}
          {step === 1 && inputMode === "natural" && (
            <div className="text-xs text-muted-foreground">
              Click "Analyze with AI" above to continue
            </div>
          )}

          {/* Step 1 Guided or Step 2/3 for any mode: Continue */}
          {((step === 1 && inputMode === "guided") ||
            (step === 2 && inputMode === "natural") ||
            (step === 2 && inputMode === "guided") ||
            step === 3) && (
            <Button
              variant="premium"
              onClick={() => {
                // NLP mode navigation
                if (inputMode === "natural") {
                  if (step === 2) setStep(3);
                  else if (step === 3) setStep(4);
                } else {
                  // Guided mode navigation
                  if (step === 1) setStep(2);
                  else if (step === 2 && !showFeatureStep) setStep(3);
                  else if (step === 2 && showFeatureStep) setStep(3);
                  else if (step === 3) setStep(4);
                }
              }}
              disabled={!canProceed()}
            >
              {step === 2 && inputMode === "natural" ? "Accept & Continue" : "Continue"}
              <ChevronRight className="h-4 w-4 ml-2" />
            </Button>
          )}

          {/* Step 4: Submit */}
          {step === 4 && (
            <Button
              variant="premium"
              onClick={handleSubmit}
              disabled={submitting}
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  <Check className="h-4 w-4 mr-2" />
                  Submit to Queue
                </>
              )}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
