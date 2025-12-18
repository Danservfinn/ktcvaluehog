"use client";

import { useState, Suspense } from "react";
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
  Lock,
  Sparkles,
  Send,
  Key,
  MessageSquare,
  Bot,
  Check,
  ExternalLink,
  Loader2,
} from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/contexts/auth-context";

// Loading fallback for Suspense
function ChatLoading() {
  return (
    <div className="space-y-8">
      <div className="flex items-center gap-3 mb-2">
        <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
          <Loader2 className="h-5 w-5 text-black animate-spin" />
        </div>
        <div className="flex items-center gap-2">
          <h1 className="text-3xl font-bold tracking-tight">Thoth AI</h1>
          <Badge variant="elite">Elite</Badge>
        </div>
      </div>
      <p className="text-muted-foreground">Loading...</p>
    </div>
  );
}

// Main page wrapper with Suspense
export default function ChatPage() {
  return (
    <Suspense fallback={<ChatLoading />}>
      <ChatContent />
    </Suspense>
  );
}

function ChatContent() {
  const { isElite, loading: authLoading } = useAuth();
  const [hasApiKey, setHasApiKey] = useState(false);
  const [message, setMessage] = useState("");

  // Show loading while auth is being checked
  if (authLoading) {
    return <ChatLoading />;
  }

  if (!isElite) {
    return (
      <div className="space-y-8">
        {/* Header */}
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
              <Sparkles className="h-5 w-5 text-black" />
            </div>
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold tracking-tight">Thoth AI</h1>
              <Badge variant="elite">Elite</Badge>
            </div>
          </div>
          <p className="text-muted-foreground">
            Your personal dynasty AI assistant powered by Claude.
          </p>
        </div>

        {/* Locked Content */}
        <Card variant="premium" className="glow-gold">
          <CardContent className="py-16 text-center">
            <div className="max-w-md mx-auto">
              <div className="h-20 w-20 rounded-2xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center mx-auto mb-6 shadow-xl shadow-amber-500/25">
                <Bot className="h-10 w-10 text-black" />
              </div>
              <h2 className="text-2xl font-bold mb-3">Meet Thoth</h2>
              <p className="text-muted-foreground mb-8 leading-relaxed">
                Chat with our AI dynasty analyst. Ask about trade advice, player
                analysis, roster construction, and more. Powered by your own
                Claude API key (BYOK).
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

        {/* Example Conversations */}
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="text-lg">What You Can Ask</CardTitle>
            <CardDescription>Example conversations with Thoth</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {[
              "Should I trade CeeDee Lamb for Bijan Robinson straight up?",
              "Who are the best buy-low RBs right now?",
              "Rate my dynasty roster and suggest improvements",
              "What rookies should I target in the 2025 draft?",
              "Is Travis Kelce still worth holding in dynasty?",
            ].map((example, i) => (
              <div
                key={i}
                className="flex items-start gap-3 p-3 bg-secondary/50 rounded-lg border border-border/50 hover:bg-secondary/70 transition-colors cursor-pointer"
              >
                <MessageSquare className="h-4 w-4 text-primary mt-0.5" />
                <p className="text-sm">{example}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* BYOK Explanation */}
        <Card variant="glass">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Key className="h-5 w-5 text-primary" />
              Bring Your Own Key (BYOK)
            </CardTitle>
            <CardDescription>How our AI integration works</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Thoth uses your own Anthropic API key for AI conversations. This
              means:
            </p>
            <ul className="text-sm space-y-2.5">
              {[
                "You control your AI costs directly with Anthropic",
                "No per-message fees from Thoth",
                "Your conversations are not stored on our servers",
                "Use the latest Claude models for best quality",
              ].map((item, i) => (
                <li key={i} className="flex items-start gap-2">
                  <Check className="h-4 w-4 text-emerald-500 mt-0.5" />
                  <span className="text-muted-foreground">{item}</span>
                </li>
              ))}
            </ul>
            <div className="pt-2">
              <Button variant="outline" size="sm" asChild>
                <a
                  href="https://console.anthropic.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Get an Anthropic API Key
                  <ExternalLink className="h-3.5 w-3.5 ml-2" />
                </a>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Elite user without API key
  if (!hasApiKey) {
    return (
      <div className="space-y-8">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
              <Sparkles className="h-5 w-5 text-black" />
            </div>
            <div className="flex items-center gap-2">
              <h1 className="text-3xl font-bold tracking-tight">Thoth AI</h1>
              <Badge variant="elite">Elite</Badge>
            </div>
          </div>
          <p className="text-muted-foreground">
            Configure your API key to start chatting.
          </p>
        </div>
        <Card variant="glass">
          <CardHeader>
            <CardTitle>Connect Your API Key</CardTitle>
            <CardDescription>
              Enter your Anthropic API key to enable Thoth AI
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input type="password" placeholder="sk-ant-..." />
            <Button variant="premium" onClick={() => setHasApiKey(true)}>
              Save API Key
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Full chat interface
  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="mb-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
            <Sparkles className="h-5 w-5 text-black" />
          </div>
          <div className="flex items-center gap-2">
            <h1 className="text-3xl font-bold tracking-tight">Thoth AI</h1>
            <Badge variant="elite">Elite</Badge>
          </div>
        </div>
      </div>
      <Card variant="elevated" className="flex-1 flex flex-col">
        <CardContent className="flex-1 p-4 overflow-y-auto">
          <div className="text-center text-muted-foreground py-8">
            <Bot className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>Start a conversation with Thoth</p>
            <p className="text-sm mt-1">
              Ask about trades, players, roster strategy...
            </p>
          </div>
        </CardContent>
        <div className="p-4 border-t border-border bg-muted/20">
          <div className="flex gap-2">
            <Input
              placeholder="Ask about trades, players, strategy..."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && message.trim()) {
                  setMessage("");
                }
              }}
            />
            <Button variant="premium" disabled={!message.trim()}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
