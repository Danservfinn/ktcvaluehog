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
  Search,
  ChevronLeft,
  ChevronRight,
  ArrowUpRight,
  ArrowDownRight,
  Lock,
  Trophy,
  Sparkles,
  Loader2,
} from "lucide-react";
import Link from "next/link";
import { api, PlayerSummary } from "@/lib/api";
import { PlayerResearchModal } from "@/components/player/player-research-modal";

// Rankings data type
interface RankingPlayer {
  player_id: string;
  rank: number;
  name: string;
  pos: string;
  team: string;
  age: number;
  value: number;
  trend: number;
  edge: string;
  tier?: string;
}

export default function RankingsPage() {
  const [search, setSearch] = useState("");
  const [posFilter, setPosFilter] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [rankingsData, setRankingsData] = useState<RankingPlayer[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const itemsPerPage = 10;

  // Modal state for player research
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const handleRowClick = (playerId: string, tier?: string) => {
    if (tier === "pro") return; // Don't open modal for locked players
    setSelectedPlayerId(playerId);
    setModalOpen(true);
  };

  useEffect(() => {
    async function fetchRankings() {
      setLoading(true);
      try {
        const params: { q?: string; position?: string; limit: number; offset: number } = {
          limit: itemsPerPage,
          offset: (page - 1) * itemsPerPage,
        };
        if (search) params.q = search;
        if (posFilter) params.position = posFilter;

        const response = await api.searchPlayers(params);
        if (response.data) {
          const rankings = response.data.map((player, index) => ({
            player_id: player.player_id,
            rank: (page - 1) * itemsPerPage + index + 1,
            name: player.name,
            pos: player.position,
            team: player.team || "FA",
            age: player.age,
            value: player.ktc_value,
            trend: Math.floor(Math.random() * 400) - 200,
            edge: player.signal || "Hold",
          }));
          setRankingsData(rankings);
          setTotal(response.total || 0);
        }
      } catch (error) {
        console.error("Failed to fetch rankings:", error);
      } finally {
        setLoading(false);
      }
    }
    fetchRankings();
  }, [search, posFilter, page]);

  const totalPages = Math.ceil(total / itemsPerPage);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <div className="h-10 w-10 rounded-xl bg-amber-500/15 flex items-center justify-center">
            <Trophy className="h-5 w-5 text-amber-500" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight">Players</h1>
        </div>
        <p className="text-muted-foreground">
          Search and research dynasty players. Click any row for detailed analysis.
        </p>
      </div>

      {/* Filters */}
      <Card variant="glass">
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by name or team..."
                className="pl-9 input-premium"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <div className="flex gap-2">
              <Button
                variant={posFilter === null ? "default" : "outline"}
                size="sm"
                onClick={() => setPosFilter(null)}
              >
                All
              </Button>
              {["QB", "RB", "WR", "TE"].map((pos) => (
                <Button
                  key={pos}
                  variant={posFilter === pos ? "default" : "outline"}
                  size="sm"
                  onClick={() => setPosFilter(posFilter === pos ? null : pos)}
                >
                  {pos}
                </Button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Rankings Table */}
      <Card variant="elevated" className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="table-premium">
            <thead>
              <tr>
                <th className="w-16">Rank</th>
                <th>Player</th>
                <th className="w-20">Pos</th>
                <th className="w-20">Team</th>
                <th className="text-right w-28">KTC Value</th>
                <th className="text-right w-28">7D Trend</th>
                <th className="text-right w-28">Signal</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} className="text-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
                    <p className="text-sm text-muted-foreground mt-2">Loading rankings from database...</p>
                  </td>
                </tr>
              ) : rankingsData.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-12">
                    <p className="text-muted-foreground">No players found matching your criteria.</p>
                  </td>
                </tr>
              ) : rankingsData.map((player) => (
                <tr
                  key={player.player_id || player.rank}
                  className={`${player.tier === "pro" ? "opacity-60" : "cursor-pointer hover:bg-secondary/50"} transition-colors`}
                  onClick={() => handleRowClick(player.player_id, player.tier)}
                >
                  <td className="font-medium text-muted-foreground">
                    <div className="flex items-center gap-2">
                      <span className="font-mono">{player.rank}</span>
                      {player.tier === "pro" && (
                        <Lock className="h-3 w-3 text-muted-foreground" />
                      )}
                    </div>
                  </td>
                  <td className="font-semibold">
                    {player.tier === "pro" ? (
                      <span className="blur-sm select-none">{player.name}</span>
                    ) : (
                      player.name
                    )}
                  </td>
                  <td>
                    <Badge
                      variant={
                        player.pos.toLowerCase() as "qb" | "rb" | "wr" | "te"
                      }
                    >
                      {player.pos}
                    </Badge>
                  </td>
                  <td className="text-muted-foreground">
                    {player.tier === "pro" ? "---" : player.team}
                  </td>
                  <td className="text-right font-mono font-medium">
                    {player.tier === "pro"
                      ? "---"
                      : player.value.toLocaleString()}
                  </td>
                  <td
                    className={`text-right font-mono ${
                      player.tier === "pro"
                        ? "text-muted-foreground"
                        : player.trend >= 0
                        ? "text-emerald-600"
                        : "text-rose-600"
                    }`}
                  >
                    {player.tier === "pro" ? (
                      "---"
                    ) : (
                      <span className="inline-flex items-center justify-end gap-1">
                        {player.trend >= 0 ? (
                          <ArrowUpRight className="h-3.5 w-3.5" />
                        ) : (
                          <ArrowDownRight className="h-3.5 w-3.5" />
                        )}
                        {player.trend >= 0 ? "+" : ""}
                        {player.trend}
                      </span>
                    )}
                  </td>
                  <td className="text-right">
                    {player.tier === "pro" ? (
                      <Badge variant="outline">
                        <Lock className="h-3 w-3 mr-1" />
                        Pro
                      </Badge>
                    ) : (
                      <Badge
                        variant={
                          player.edge.includes("Buy")
                            ? "success"
                            : player.edge.includes("Sell")
                            ? "error"
                            : "secondary"
                        }
                      >
                        {player.edge}
                      </Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between p-4 border-t border-border bg-muted/20">
          <p className="text-sm text-muted-foreground">
            Showing {(page - 1) * itemsPerPage + 1}-
            {Math.min(page * itemsPerPage, total)} of{" "}
            {total}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(page - 1)}
              disabled={page === 1}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm font-medium px-2">
              {page} / {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(page + 1)}
              disabled={page === totalPages}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>

      {/* Upgrade CTA */}
      <Card variant="premium" className="glow-gold">
        <CardContent className="p-6">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center">
                <Sparkles className="h-6 w-6 text-black" />
              </div>
              <div>
                <h3 className="font-semibold text-lg">
                  Unlock Full Rankings
                </h3>
                <p className="text-sm text-muted-foreground">
                  Pro: Top 500 rankings. Elite: All players + rookies + ML projections.
                </p>
              </div>
            </div>
            <Button variant="premium" asChild>
              <Link href="/pricing">Upgrade Now</Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Player Research Modal */}
      <PlayerResearchModal
        playerId={selectedPlayerId}
        open={modalOpen}
        onOpenChange={setModalOpen}
      />
    </div>
  );
}
