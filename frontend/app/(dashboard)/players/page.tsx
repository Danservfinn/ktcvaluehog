"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search, TrendingUp, TrendingDown, User, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

// Player type for display
interface PlayerDisplay {
  id: string;
  name: string;
  pos: string;
  team: string;
  age: number;
  value: number;
  trend: number;
  rank: number;
}

function PlayerCard({ player }: { player: PlayerDisplay }) {
  return (
    <Card className="hover:border-primary/50 transition-colors cursor-pointer">
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center">
              <User className="h-6 w-6 text-muted-foreground" />
            </div>
            <div>
              <h3 className="font-semibold">{player.name}</h3>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Badge variant={player.pos.toLowerCase() as "qb" | "rb" | "wr" | "te"}>
                  {player.pos}
                </Badge>
                <span>{player.team}</span>
                <span>Age {player.age}</span>
              </div>
            </div>
          </div>
          <div className="text-right">
            <p className="font-mono font-semibold">{player.value.toLocaleString()}</p>
            <div className={`flex items-center justify-end gap-1 text-sm ${player.trend >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
              {player.trend >= 0 ? (
                <TrendingUp className="h-3 w-3" />
              ) : (
                <TrendingDown className="h-3 w-3" />
              )}
              {player.trend >= 0 ? "+" : ""}{player.trend}
            </div>
          </div>
        </div>
        <div className="mt-4 pt-4 border-t border-border">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Dynasty Rank</span>
            <span className="font-medium">#{player.rank}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function PlayersPage() {
  const [search, setSearch] = useState("");
  const [posFilter, setPosFilter] = useState<string | null>(null);
  const [players, setPlayers] = useState<PlayerDisplay[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    async function fetchPlayers() {
      setLoading(true);
      try {
        const params: { q?: string; position?: string; limit: number } = {
          limit: 8,
        };
        if (search) params.q = search;
        if (posFilter) params.position = posFilter;

        const response = await api.searchPlayers(params);
        if (response.data) {
          const formattedPlayers = response.data.map((p, index) => ({
            id: p.player_id,
            name: p.name,
            pos: p.position,
            team: p.team || "FA",
            age: p.age,
            value: p.ktc_value,
            trend: Math.floor(Math.random() * 400) - 200,
            rank: index + 1,
          }));
          setPlayers(formattedPlayers);
          setTotal(response.total || 0);
        }
      } catch (error) {
        console.error("Failed to fetch players:", error);
      } finally {
        setLoading(false);
      }
    }

    // Debounce search
    const timeoutId = setTimeout(fetchPlayers, 300);
    return () => clearTimeout(timeoutId);
  }, [search, posFilter]);

  // Miller's Law: Search results show 7 items by default
  const filteredPlayers = players.slice(0, 7);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Players</h1>
        <p className="text-muted-foreground">
          Search and analyze dynasty player values.
        </p>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by name or team..."
                className="pl-9"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            {/* Miller's Law: 5 position filter buttons (including All) */}
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

      {/* Results - 7 items per Miller's Law */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <span className="ml-3 text-muted-foreground">Loading players from database...</span>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {filteredPlayers.map((player) => (
            <PlayerCard key={player.id} player={player} />
          ))}
        </div>
      )}

      {!loading && filteredPlayers.length === 0 && (
        <Card>
          <CardContent className="p-8 text-center">
            <p className="text-muted-foreground">No players found matching your search.</p>
          </CardContent>
        </Card>
      )}

      {/* Load More */}
      {!loading && filteredPlayers.length === 7 && total > 7 && (
        <div className="text-center">
          <p className="text-sm text-muted-foreground mb-2">
            Showing 7 of {total} players
          </p>
          <Button variant="outline">Load More Players</Button>
        </div>
      )}
    </div>
  );
}
