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
  Key,
  Link2,
  User,
  CreditCard,
  Eye,
  EyeOff,
  Check,
  Sparkles,
  Trash2,
  Settings,
  Shield,
  ExternalLink,
  AlertCircle,
} from "lucide-react";
import {
  getAnthropicKey,
  setAnthropicKey,
  removeAnthropicKey,
  maskApiKey,
  isValidKeyFormat,
} from "@/lib/byok";

export default function SettingsPage() {
  const [showApiKey, setShowApiKey] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [savedKey, setSavedKey] = useState<string | null>(null);
  const [keyError, setKeyError] = useState<string | null>(null);
  const [leagueId, setLeagueId] = useState("");
  const [connectedLeagues, setConnectedLeagues] = useState<string[]>([]);

  // Load saved key from localStorage on mount
  useEffect(() => {
    const stored = getAnthropicKey();
    if (stored) {
      setSavedKey(stored);
    }
  }, []);

  const handleSaveApiKey = () => {
    if (!apiKey) return;

    setKeyError(null);

    if (!isValidKeyFormat(apiKey)) {
      setKeyError("Invalid API key format. Keys should start with 'sk-ant-'");
      return;
    }

    try {
      setAnthropicKey(apiKey);
      setSavedKey(apiKey);
      setApiKey("");
    } catch (err: any) {
      setKeyError(err.message || "Failed to save API key");
    }
  };

  const handleRemoveApiKey = () => {
    removeAnthropicKey();
    setSavedKey(null);
  };

  const handleConnectLeague = () => {
    if (leagueId && !connectedLeagues.includes(leagueId)) {
      setConnectedLeagues([...connectedLeagues, leagueId]);
      setLeagueId("");
    }
  };

  const handleRemoveLeague = (id: string) => {
    setConnectedLeagues(connectedLeagues.filter((l) => l !== id));
  };

  return (
    <div className="space-y-8 max-w-3xl">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <div className="h-10 w-10 rounded-xl bg-secondary flex items-center justify-center">
            <Settings className="h-5 w-5 text-muted-foreground" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        </div>
        <p className="text-muted-foreground">
          Manage your account, subscriptions, and integrations.
        </p>
      </div>

      {/* Section 1: Profile */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <User className="h-5 w-5 text-primary" />
            Profile
          </CardTitle>
          <CardDescription>Your account information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="text-sm font-medium">Email</label>
              <Input
                type="email"
                value="user@example.com"
                disabled
                className="mt-1.5"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Username</label>
              <Input value="DynastyManager" className="mt-1.5" />
            </div>
          </div>
          <Button variant="outline">Update Profile</Button>
        </CardContent>
      </Card>

      {/* Section 2: Subscription */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <CreditCard className="h-5 w-5 text-primary" />
            Subscription
          </CardTitle>
          <CardDescription>Your current plan and billing</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-xl border border-border">
            <div>
              <p className="font-medium">Free Plan</p>
              <p className="text-sm text-muted-foreground">
                Top 100 rankings, 3 trades/day
              </p>
            </div>
            <Badge variant="free">Current</Badge>
          </div>
          <div className="flex gap-3">
            <Button variant="default">
              <Sparkles className="h-4 w-4 mr-2" />
              Upgrade to Pro
            </Button>
            <Button variant="premium">
              <Sparkles className="h-4 w-4 mr-2" />
              Go Elite
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Section 3: API Key (BYOK) */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Key className="h-5 w-5 text-primary" />
            Anthropic API Key
            <Badge variant="elite">Elite</Badge>
          </CardTitle>
          <CardDescription>
            Connect your Claude API key for Thoth AI (BYOK - Bring Your Own Key)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {savedKey ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl">
                <div className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-emerald-500" />
                  <span className="text-sm font-medium">API Key Connected</span>
                </div>
                <code className="text-sm text-muted-foreground font-mono">
                  {maskApiKey(savedKey)}
                </code>
              </div>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleRemoveApiKey}
              >
                Remove Key
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="relative">
                <Input
                  type={showApiKey ? "text" : "password"}
                  placeholder="sk-ant-api03-..."
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                />
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="absolute right-2 top-1/2 -translate-y-1/2"
                  onClick={() => setShowApiKey(!showApiKey)}
                >
                  {showApiKey ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </Button>
              </div>
              {keyError && (
                <div className="flex items-center gap-2 text-sm text-rose-500">
                  <AlertCircle className="h-4 w-4" />
                  {keyError}
                </div>
              )}
              <div className="flex items-center gap-3">
                <Button onClick={handleSaveApiKey} disabled={!apiKey}>
                  Save API Key
                </Button>
                <Button variant="link" size="sm" asChild>
                  <a
                    href="https://console.anthropic.com/settings/keys"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Get an API Key
                    <ExternalLink className="h-3.5 w-3.5 ml-1.5" />
                  </a>
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Your API key is stored locally in your browser and never sent to
                our servers. You pay Anthropic directly for AI usage.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Section 4: League Connections */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Link2 className="h-5 w-5 text-primary" />
            League Connections
          </CardTitle>
          <CardDescription>
            Connect your Sleeper leagues for personalized insights
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="Sleeper League ID"
              value={leagueId}
              onChange={(e) => setLeagueId(e.target.value)}
            />
            <Button onClick={handleConnectLeague} disabled={!leagueId}>
              Connect
            </Button>
          </div>

          {connectedLeagues.length > 0 ? (
            <div className="space-y-2">
              {connectedLeagues.map((id) => (
                <div
                  key={id}
                  className="flex items-center justify-between p-3 bg-secondary/50 rounded-lg border border-border/50"
                >
                  <div className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-emerald-500" />
                    <span className="text-sm font-medium">League {id}</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    className="text-muted-foreground hover:text-destructive"
                    onClick={() => handleRemoveLeague(id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground text-center py-4">
              No leagues connected. Add your Sleeper league ID above.
            </p>
          )}

          <p className="text-xs text-muted-foreground">
            Free tier: 1 league | Pro: 3 leagues | Elite: Unlimited
          </p>
        </CardContent>
      </Card>

      {/* Section 5: Data & Privacy */}
      <Card variant="glass">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            Data & Privacy
          </CardTitle>
          <CardDescription>Manage your data</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-xl border border-border/50">
            <div>
              <p className="font-medium">Export Your Data</p>
              <p className="text-sm text-muted-foreground">
                Download all your Thoth data
              </p>
            </div>
            <Button variant="outline" size="sm">
              Export
            </Button>
          </div>
          <div className="flex items-center justify-between p-4 bg-rose-500/5 rounded-xl border border-rose-500/20">
            <div>
              <p className="font-medium text-rose-400">Delete Account</p>
              <p className="text-sm text-muted-foreground">
                Permanently delete your account and data
              </p>
            </div>
            <Button variant="destructive" size="sm">
              Delete
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
