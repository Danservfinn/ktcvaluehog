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
} from "lucide-react";

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
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);

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
      const [typesRes, featuresRes] = await Promise.all([
        fetch(`${apiBase}/api/v1/ml-monitor/hypothesis-types`),
        fetch(`${apiBase}/api/v1/ml-monitor/features/categories`),
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
    } catch (error) {
      console.error("Failed to fetch hypothesis builder data:", error);
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setStep(1);
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
                  Step {step} of 4 - Configure your ML improvement experiment
                </DialogDescription>
              </div>
            </div>
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
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-6">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : (
            <>
              {/* Step 1: Select Type */}
              {step === 1 && (
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

              {/* Step 2: Feature Selection (conditional) */}
              {step === 2 && showFeatureStep && (
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

              {/* Step 2 (non-feature) or Step 3: Details */}
              {((step === 2 && !showFeatureStep) || step === 3) && (
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
            onClick={() => step === 1 ? handleClose() : setStep(step - 1)}
          >
            <ChevronLeft className="h-4 w-4 mr-2" />
            {step === 1 ? "Cancel" : "Back"}
          </Button>

          {step < 4 ? (
            <Button
              variant="premium"
              onClick={() => {
                if (step === 2 && !showFeatureStep) {
                  setStep(3);
                } else if (step === 3) {
                  setStep(4);
                } else {
                  setStep(step + 1);
                }
              }}
              disabled={!canProceed()}
            >
              Continue
              <ChevronRight className="h-4 w-4 ml-2" />
            </Button>
          ) : (
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
