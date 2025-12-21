"use client";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Check, X, ArrowLeft, Sparkles, LogIn } from "lucide-react";
import Link from "next/link";

// Thoth Logo Component
function ThothLogo() {
  return (
    <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-amber-400 via-yellow-400 to-amber-500 flex items-center justify-center shadow-lg shadow-amber-500/25">
      <svg
        viewBox="0 0 24 24"
        fill="none"
        className="h-6 w-6 text-black"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 2L2 7l10 5 10-5-10-5z" />
        <path d="M2 17l10 5 10-5" />
        <path d="M2 12l10 5 10-5" />
      </svg>
    </div>
  );
}

const features = [
  { name: "Player Search", free: true, pro: true, elite: true },
  {
    name: "Dynasty Rankings",
    free: "Top 100",
    pro: "Top 500",
    elite: "All + Rookies",
  },
  {
    name: "Player Profiles",
    free: "Basic",
    pro: "Full + Athletic",
    elite: "Full + Contract",
  },
  {
    name: "Trade Analyzer",
    free: "3/day",
    pro: "Unlimited",
    elite: "Unlimited + ML",
  },
  { name: "ML Projections", free: false, pro: false, elite: true },
  { name: "Thoth AI (BYOK)", free: false, pro: false, elite: true },
  { name: "Data Export", free: false, pro: false, elite: "CSV + API" },
];

function FeatureValue({ value }: { value: boolean | string }) {
  if (value === true) {
    return <Check className="h-5 w-5 text-emerald-500" />;
  }
  if (value === false) {
    return <X className="h-5 w-5 text-muted-foreground/30" />;
  }
  return <span className="text-sm font-medium">{value}</span>;
}

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="border-b border-border/40 backdrop-blur-xl fixed top-0 w-full z-50 bg-background/80">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3">
            <ThothLogo />
            <span className="font-bold text-xl">Thoth</span>
          </Link>
          <div className="flex items-center gap-2">
            <Button asChild>
              <Link href="/login">
                <LogIn className="h-4 w-4 mr-2" />
                Login
              </Link>
            </Button>
            <Button variant="ghost" asChild>
              <Link href="/">
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Link>
            </Button>
          </div>
        </div>
      </nav>

      {/* Header */}
      <section className="pt-32 pb-12 px-4 text-center">
        <Badge variant="secondary" className="mb-4">
          Pricing
        </Badge>
        <h1 className="text-4xl sm:text-5xl font-bold mb-4 tracking-tight">
          Choose Your <span className="text-gradient-gold">Plan</span>
        </h1>
        <p className="text-muted-foreground max-w-2xl mx-auto text-lg">
          Start free and upgrade as you need more features. All plans include
          our core dynasty analytics.
        </p>
      </section>

      {/* Pricing Cards */}
      <section className="pb-20 px-4">
        <div className="mx-auto max-w-5xl">
          <div className="grid md:grid-cols-3 gap-6">
            {/* Free Tier */}
            <Card variant="glass" className="relative card-hover">
              <CardHeader className="text-center pb-4">
                <CardTitle className="text-2xl">Free</CardTitle>
                <CardDescription>For casual managers</CardDescription>
                <div className="pt-4">
                  <span className="text-5xl font-bold">$0</span>
                  <span className="text-muted-foreground">/month</span>
                </div>
              </CardHeader>
              <CardContent>
                <ul className="space-y-4 mb-6">
                  {features.map((feature) => (
                    <li
                      key={feature.name}
                      className="flex items-center justify-between"
                    >
                      <span className="text-sm text-muted-foreground">
                        {feature.name}
                      </span>
                      <FeatureValue value={feature.free} />
                    </li>
                  ))}
                </ul>
                <Button className="w-full" variant="outline" asChild>
                  <Link href="/dashboard">Get Started</Link>
                </Button>
              </CardContent>
            </Card>

            {/* Pro Tier */}
            <Card
              variant="glass"
              className="relative card-hover border-cyan-500/30"
            >
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <Badge variant="pro">Most Popular</Badge>
              </div>
              <CardHeader className="text-center pb-4">
                <CardTitle className="text-2xl">Pro</CardTitle>
                <CardDescription>For competitive managers</CardDescription>
                <div className="pt-4">
                  <span className="text-5xl font-bold">$9.99</span>
                  <span className="text-muted-foreground">/month</span>
                </div>
              </CardHeader>
              <CardContent>
                <ul className="space-y-4 mb-6">
                  {features.map((feature) => (
                    <li
                      key={feature.name}
                      className="flex items-center justify-between"
                    >
                      <span className="text-sm text-muted-foreground">
                        {feature.name}
                      </span>
                      <FeatureValue value={feature.pro} />
                    </li>
                  ))}
                </ul>
                <Button className="w-full" asChild>
                  <Link href="/dashboard">Upgrade to Pro</Link>
                </Button>
              </CardContent>
            </Card>

            {/* Elite Tier */}
            <Card variant="premium" className="relative card-hover glow-gold">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <Badge variant="elite">
                  <Sparkles className="h-3 w-3 mr-1" />
                  Elite
                </Badge>
              </div>
              <CardHeader className="text-center pb-4">
                <CardTitle className="text-2xl">Elite</CardTitle>
                <CardDescription>For dynasty champions</CardDescription>
                <div className="pt-4">
                  <span className="text-5xl font-bold">$19.99</span>
                  <span className="text-muted-foreground">/month</span>
                </div>
              </CardHeader>
              <CardContent>
                <ul className="space-y-4 mb-6">
                  {features.map((feature) => (
                    <li
                      key={feature.name}
                      className="flex items-center justify-between"
                    >
                      <span className="text-sm text-muted-foreground">
                        {feature.name}
                      </span>
                      <FeatureValue value={feature.elite} />
                    </li>
                  ))}
                </ul>
                <Button className="w-full" variant="premium" asChild>
                  <Link href="/dashboard">Go Elite</Link>
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Secondary login prompt for scrolled users */}
          <p className="text-center mt-8 text-muted-foreground">
            Already have an account?{" "}
            <Link
              href="/login"
              className="text-primary font-medium hover:underline underline-offset-4"
            >
              Log in
            </Link>
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-16 px-4 bg-muted/20">
        <div className="mx-auto max-w-3xl">
          <h2 className="text-2xl font-bold text-center mb-8">
            Frequently Asked Questions
          </h2>
          <div className="space-y-4">
            {[
              {
                q: "What is BYOK (Bring Your Own Key)?",
                a: "Elite tier uses your own Anthropic API key for Thoth AI. This means you pay Anthropic directly for AI usage and we never see your API key. It's stored locally in your browser.",
              },
              {
                q: "Can I cancel anytime?",
                a: "Yes, you can cancel your subscription at any time. You'll retain access until the end of your billing period.",
              },
              {
                q: "How often is data updated?",
                a: "KTC values are updated twice daily (6 AM and 6 PM UTC). ML models are retrained weekly.",
              },
              {
                q: "Do you offer annual pricing?",
                a: "Not yet, but it's coming soon with a 20% discount for annual subscriptions.",
              },
            ].map((faq, i) => (
              <Card key={i} variant="glass">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{faq.q}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">{faq.a}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-8 px-4">
        <div className="mx-auto max-w-7xl flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-amber-400 to-amber-500 flex items-center justify-center">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                className="h-5 w-5 text-black"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <span className="font-semibold">Thoth</span>
          </div>
          <div className="text-sm text-muted-foreground">
            &copy; {new Date().getFullYear()} Thoth Analytics. All rights
            reserved.
          </div>
        </div>
      </footer>
    </div>
  );
}
