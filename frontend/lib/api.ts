/**
 * Dynasty Edge API Client
 * Handles all communication with the FastAPI backend
 */

import { getAuthToken } from './supabase'
import { getAnthropicKey as getStoredKey } from './byok'

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://dynasty-api-production.up.railway.app";

export interface Player {
  player_id: string;
  name: string;
  position: string;
  team: string | null;
  age: number;
  ktc_value: number;
  ktc_rank?: number;
  signal?: string;
  edge_score?: number;
  predicted_value?: number;
  trend_value?: number;
}

export interface PlayerSummary {
  player_id: string;
  name: string;
  position: string;
  team: string | null;
  age: number;
  ktc_value: number;
  signal?: string;
}

export interface TradeAnalysis {
  give_side: {
    players: PlayerSummary[];
    total_ktc_value: number;
    total_predicted_value?: number;
    average_age?: number;
  };
  get_side: {
    players: PlayerSummary[];
    total_ktc_value: number;
    total_predicted_value?: number;
    average_age?: number;
  };
  ktc_differential: number;
  predicted_differential?: number;
  recommendation: 'ACCEPT' | 'REJECT' | 'FAIR';
  confidence: number;
  reasoning: string;
}

export interface Projection {
  player_id: string;
  name: string;
  position: string;
  team: string | null;
  age: number;
  ktc_value: number;
  projected_points: number;
  projected_ppg: number;
  confidence: number;
  ceiling: number;
  floor: number;
  games_projected?: number;
  projection_rank?: number;
}

// Elite Trade Analysis Types
export interface PlayerValueAnalysis {
  current_value: number;
  value_rank?: number;
  value_30d_change?: number;
  value_90d_change?: number;
  value_trend?: 'rising' | 'stable' | 'falling';
  projected_value_1yr?: number;
  projected_value_2yr?: number;
  projected_value_3yr?: number;
}

export interface PlayerProductionProfile {
  season_ppg?: number;
  last_4_ppg?: number;
  ppg_trend?: string;
  consistency_score?: number;
  boom_rate?: number;
  bust_rate?: number;
  epa_per_touch?: number;
  target_share?: number;
  touch_share?: number;
  red_zone_share?: number;
  wopr?: number;
  adot?: number;
}

export interface PlayerDynastyOutlook {
  age?: number;
  years_in_peak?: number;
  peak_window?: string;
  aging_curve_position?: 'Pre-Peak' | 'Peak' | 'Post-Peak' | 'Declining';
  projected_ppg?: number;
  projection_floor?: number;
  projection_ceiling?: number;
  projection_confidence?: number;
  projected_pos_rank?: number;
}

export interface PlayerRiskAssessment {
  injury_burden_score?: number;
  injury_risk_level?: 'Low' | 'Medium' | 'High';
  games_missed_3yr?: number;
  key_injury_concerns?: string;
  situation_score?: number;
  qb_situation?: string;
  team_stability?: string;
  depth_chart_security?: 'Locked' | 'Secure' | 'At Risk';
}

export interface ElitePlayerAnalysis {
  player_id: string;
  name: string;
  position: string;
  team?: string;
  age?: number;
  value: PlayerValueAnalysis;
  production: PlayerProductionProfile;
  dynasty: PlayerDynastyOutlook;
  risk: PlayerRiskAssessment;
  overall_grade?: string;
  one_liner?: string;
}

export interface EliteTradeSide {
  players: ElitePlayerAnalysis[];
  total_current_value: number;
  total_projected_value_1yr?: number;
  total_projected_value_3yr?: number;
  average_age?: number;
  composite_risk_score?: number;
}

export interface TradeScoreBreakdown {
  current_value_edge: number;
  projected_value_edge: number;
  production_edge: number;
  age_edge: number;
  risk_edge: number;
  total_edge: number;
}

export interface TradeNarrative {
  introduction: string;
  player_analysis_give: string[];
  player_analysis_get: string[];
  value_analysis: string;
  dynasty_outlook: string;
  risk_assessment: string;
  recommendation: string;
  closing: string;
}

export interface EliteTradeAnalysis {
  verdict: 'WIN' | 'LOSE' | 'FAIR';
  verdict_score: number;
  confidence: number;
  executive_summary: string;
  best_for: 'Rebuild' | 'Contend' | 'Either';
  risk_level: 'Low' | 'Medium' | 'High';
  give_side: EliteTradeSide;
  get_side: EliteTradeSide;
  score_breakdown: TradeScoreBreakdown;
  key_insights: string[];
  recommendation_accept_if: string[];
  recommendation_decline_if: string[];
  suggested_additions?: string;
  similar_trade_note?: string;
  written_report?: TradeNarrative;
}

// Player Research Types (for modal display)
export interface ResearchValueAnalysis {
  current_value: number;
  value_rank?: number;
  positional_rank?: number;
  value_30d_change?: number;
  value_trend?: 'rising' | 'stable' | 'falling';
  projected_value_1yr?: number;
  projected_value_2yr?: number;
  projected_value_3yr?: number;
}

export interface ResearchProductionProfile {
  season_ppg?: number;
  games_played?: number;
  total_points?: number;
  targets?: number;
  receptions?: number;
  receiving_yards?: number;
  receiving_tds?: number;
  carries?: number;
  rushing_yards?: number;
  rushing_tds?: number;
  target_share?: number;
  touch_share?: number;
  red_zone_share?: number;
  epa_per_touch?: number;
  wopr?: number;
  adot?: number;
}

export interface CareerProjection {
  year: number;
  age: number;
  projected_ktc: number;
  projected_ppg: number | null;
}

export interface ResearchDynastyOutlook {
  years_in_peak?: number;
  peak_window?: string;
  aging_curve_position?: 'Pre-Peak' | 'Peak' | 'Post-Peak' | 'Declining';
  projected_ppg?: number;
  projection_floor?: number;
  projection_ceiling?: number;
  projection_confidence?: number;
  career_projections?: CareerProjection[];
}

export interface ResearchRiskAssessment {
  injury_burden_score?: number;
  injury_risk_level?: 'Low' | 'Medium' | 'High';
  games_missed_3yr?: number;
  starter_rate?: number;
  depth_chart_security?: 'Locked' | 'Secure' | 'At Risk';
}

export interface ResearchAthleticProfile {
  forty_time?: number;
  vertical_jump?: number;
  broad_jump?: number;
  three_cone?: number;
  shuttle?: number;
  bench_press?: number;
  height?: number;
  weight?: number;
  draft_round?: number;
  draft_pick?: number;
  draft_year?: number;
}

export interface PlayerResearch {
  player_id: string;
  name: string;
  position: string;
  team?: string;
  age?: number;
  experience?: number;
  college?: string;
  value: ResearchValueAnalysis;
  production: ResearchProductionProfile;
  dynasty: ResearchDynastyOutlook;
  risk: ResearchRiskAssessment;
  athletic?: ResearchAthleticProfile;
  overall_grade?: string;
  one_liner?: string;
}

// League Analysis Types
export interface SleeperLeague {
  league_id: string;
  name: string;
  season: string;
  status: string;
  total_rosters: number;
  roster_positions: string[];
  scoring_settings: Record<string, number>;
  settings: Record<string, unknown>;
}

export interface LeagueConnectResponse {
  user_id: string;
  username: string;
  leagues: SleeperLeague[];
}

export interface LeaguePlayerAnalysis {
  player_id: string;
  sleeper_id?: string;
  name: string;
  position: string;
  team?: string;
  age?: number;
  ktc_value: number;
  projected_ppg?: number;
  years_until_peak?: number;
  years_in_peak?: number;
  career_phase?: string;
  is_starter: boolean;
  is_breakout_candidate: boolean;
  is_sell_candidate: boolean;
}

export interface PositionalStrength {
  position: string;
  starter_value: number;
  starter_ppg: number;
  depth_value: number;
  depth_ppg: number;
  total_value: number;
  player_count: number;
  grade: string;
}

export interface RosterAnalysis {
  roster_id: number;
  owner_id?: string;
  team_name: string;
  players: LeaguePlayerAnalysis[];
  starters: LeaguePlayerAnalysis[];
  bench: LeaguePlayerAnalysis[];
  total_ktc_value: number;
  total_projected_ppg: number;
  starter_ppg: number;
  positional_strength: PositionalStrength[];
  average_age: number;
  future_picks: { year: number; round: number; original_owner: number; value: number }[];
  draft_capital_value: number;
  classification: 'CONTENDER' | 'FRINGE' | 'REBUILDER';
  dynasty_health_score: number;
  championship_probability: number;
}

export interface DynastyHealthBreakdown {
  total_score: number;
  age_score: number;
  peak_overlap_score: number;
  injury_risk_score: number;
  position_wins_score: number;
  draft_capital_score: number;
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
}

export interface ChampionshipSimulation {
  simulations_run: number;
  playoff_probability: number;
  bye_probability: number;
  championship_probability: number;
  seed_probabilities: Record<number, number>;
  expected_wins: number;
  expected_points_for: number;
  best_case_record: string;
  worst_case_record: string;
  most_likely_record: string;
}

export interface TradeTarget {
  player: LeaguePlayerAnalysis;
  owner_roster_id: number;
  owner_team_name: string;
  trade_value: number;
  fit_score: number;
  availability_score: number;
}

export interface TradeSuggestion {
  give_players: LeaguePlayerAnalysis[];
  get_players: LeaguePlayerAnalysis[];
  give_value: number;
  get_value: number;
  value_differential: number;
  your_ppg_change: number;
  their_ppg_change: number;
  your_championship_change: number;
  rationale: string;
  win_win_score: number;
}

export interface TradePartner {
  roster_id: number;
  team_name: string;
  owner_name: string;
  weak_positions: string[];
  trade_targets: TradeTarget[];
  suggestions: TradeSuggestion[];
  compatibility_score: number;
}

export interface PowerRanking {
  rank: number;
  roster_id: number;
  team_name: string;
  owner_name: string;
  ktc_value: number;
  projected_value: number;
  dynasty_health_score: number;
  championship_probability: number;
  classification: 'CONTENDER' | 'FRINGE' | 'REBUILDER';
  value_trend: string;
}

export interface LeagueAnalysis {
  league_id: string;
  league_name: string;
  season: string;
  scoring_type: 'ppr' | 'half_ppr' | 'standard';
  total_teams: number;
  your_roster_id: number;
  your_analysis: RosterAnalysis;
  your_dynasty_health: DynastyHealthBreakdown;
  your_championship_odds: ChampionshipSimulation;
  power_rankings: PowerRanking[];
  trade_partners: TradePartner[];
  top_trade_suggestions: TradeSuggestion[];
  buy_low_targets: TradeTarget[];
  sell_high_candidates: LeaguePlayerAnalysis[];
  waiver_targets: LeaguePlayerAnalysis[];
  analysis_timestamp: string;
  data_freshness: string;
}

export interface PaginatedResponse<T> {
  success: boolean;
  data: T[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}

class ApiClient {
  private baseUrl: string;

  constructor() {
    this.baseUrl = API_URL;
  }

  private async fetch<T>(
    endpoint: string,
    options: RequestInit = {},
    requireAuth = false,
    includeAnthropicKey = false
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    // Add auth token if available
    if (requireAuth) {
      const token = await getAuthToken();
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      } else if (requireAuth) {
        throw new Error("Authentication required");
      }
    }

    // Add Anthropic key for AI features (BYOK)
    if (includeAnthropicKey) {
      const anthropicKey = getStoredKey();
      if (anthropicKey) {
        headers["X-Anthropic-Key"] = anthropicKey;
      }
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `API Error: ${response.status}`);
    }

    return response.json();
  }

  // Health check
  async health(): Promise<{ status: string; version: string; database: string; node_count: number }> {
    return this.fetch('/api/v1/health');
  }

  // Player endpoints
  async searchPlayers(params: {
    q?: string;
    position?: string;
    team?: string;
    min_age?: number;
    max_age?: number;
    min_ktc?: number;
    max_ktc?: number;
    signal?: string;
    limit?: number;
    offset?: number;
  }): Promise<PaginatedResponse<PlayerSummary>> {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) searchParams.append(key, String(value));
    });
    return this.fetch(`/api/v1/players/search?${searchParams}`);
  }

  async getPlayer(id: string): Promise<ApiResponse<Player>> {
    return this.fetch(`/api/v1/players/${id}`);
  }

  async getValueHistory(id: string, days = 90): Promise<ApiResponse<{ date: string; value: number }[]>> {
    return this.fetch(`/api/v1/players/${id}/value-history?days=${days}`);
  }

  async getPlayerResearch(id: string): Promise<ApiResponse<PlayerResearch>> {
    return this.fetch(`/api/v1/players/${id}/research`);
  }

  async comparePlayers(playerIds: string[]): Promise<ApiResponse<{ players: Player[]; comparison_summary: string }>> {
    return this.fetch('/api/v1/players/compare', {
      method: 'POST',
      body: JSON.stringify(playerIds),
    });
  }

  // Rankings endpoints (tier-gated)
  async getRankings(params: {
    position?: string;
    limit?: number;
    offset?: number;
    include_rookies?: boolean;
  } = {}): Promise<PaginatedResponse<Player>> {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) searchParams.append(key, String(value));
    });
    return this.fetch(`/api/v1/rankings?${searchParams}`, {}, true);
  }

  async getPositionalRankings(position: string, limit = 50): Promise<PaginatedResponse<Player>> {
    return this.fetch(`/api/v1/rankings/positional/${position}?limit=${limit}`, {}, true);
  }

  async getRisers(days = 7, limit = 25): Promise<PaginatedResponse<Player>> {
    return this.fetch(`/api/v1/rankings/risers?days=${days}&limit=${limit}`);
  }

  async getFallers(days = 7, limit = 25): Promise<PaginatedResponse<Player>> {
    return this.fetch(`/api/v1/rankings/fallers?days=${days}&limit=${limit}`);
  }

  // Signals endpoints
  async getEdgeSignals(params: {
    signal?: string;
    position?: string;
    min_edge?: number;
    max_edge?: number;
    limit?: number;
  } = {}): Promise<PaginatedResponse<Player>> {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) searchParams.append(key, String(value));
    });
    return this.fetch(`/api/v1/signals/edge?${searchParams}`);
  }

  async getBuyTargets(position?: string, minEdge = 10, limit = 25): Promise<PaginatedResponse<Player>> {
    const params = new URLSearchParams({ min_edge: String(minEdge), limit: String(limit) });
    if (position) params.append('position', position);
    return this.fetch(`/api/v1/signals/buy-targets?${params}`);
  }

  async getSellCandidates(position?: string, maxEdge = -10, limit = 25): Promise<PaginatedResponse<Player>> {
    const params = new URLSearchParams({ max_edge: String(maxEdge), limit: String(limit) });
    if (position) params.append('position', position);
    return this.fetch(`/api/v1/signals/sell-candidates?${params}`);
  }

  // Trade endpoints
  async analyzeTrade(give: string[], get: string[]): Promise<ApiResponse<TradeAnalysis>> {
    return this.fetch('/api/v1/trades/analyze', {
      method: 'POST',
      body: JSON.stringify({ give, get }),
    }, true);
  }

  async analyzeTradeElite(
    give: string[],
    get: string[],
    options: { superflex?: boolean; tep?: boolean } = {}
  ): Promise<ApiResponse<EliteTradeAnalysis>> {
    // Note: Auth check is done on frontend (isElite), backend is open
    return this.fetch('/api/v1/trades/analyze-elite', {
      method: 'POST',
      body: JSON.stringify({
        give,
        get,
        superflex: options.superflex || false,
        tep: options.tep || false,
      }),
    });
  }

  async enhanceTradeNarrative(analysis: EliteTradeAnalysis): Promise<Response> {
    /**
     * Get AI-enhanced narrative for a trade analysis.
     * Uses Claude Opus 4.5 via BYOK (Bring Your Own Key).
     * Returns raw Response for streaming.
     */
    const anthropicKey = getStoredKey();
    if (!anthropicKey) {
      throw new Error('Anthropic API key required. Add it in Settings.');
    }

    return fetch(`${this.baseUrl}/api/v1/trades/analyze-elite/enhance`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Anthropic-Key': anthropicKey,
      },
      body: JSON.stringify({ analysis }),
    });
  }

  async findTradeTargets(position: string, budgetKtc: number, signal = 'BUY'): Promise<ApiResponse<Player[]>> {
    return this.fetch(`/api/v1/trades/targets?position=${position}&budget_ktc=${budgetKtc}&signal=${signal}`);
  }

  // Projections endpoints (Elite only)
  async getProjections(params: {
    position?: string;
    season?: number;
    limit?: number;
    offset?: number;
    sort_by?: 'projected_points' | 'projected_ppg' | 'confidence';
  } = {}): Promise<PaginatedResponse<Projection>> {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) searchParams.append(key, String(value));
    });
    const queryString = searchParams.toString();
    return this.fetch(`/api/v1/projections${queryString ? `?${queryString}` : ''}`, {}, true);
  }

  async getWeeklyProjections(params: {
    week: number;
    position?: string;
    limit?: number;
  }): Promise<PaginatedResponse<Projection>> {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) searchParams.append(key, String(value));
    });
    return this.fetch(`/api/v1/projections/weekly?${searchParams}`, {}, true);
  }

  async getModelInfo(): Promise<{
    model_type: string;
    r_squared: number;
    baseline_r_squared: number;
    training_data: { seasons: string; samples: string };
    positions_covered: string[];
  }> {
    return this.fetch('/api/v1/projections/model-info');
  }

  // Chat endpoints (Elite only, BYOK)
  async chat(message: string, history: { role: string; content: string }[] = []): Promise<Response> {
    const token = await getAuthToken();
    const anthropicKey = getStoredKey();

    if (!token) throw new Error('Authentication required');
    if (!anthropicKey) throw new Error('Anthropic API key required. Add it in Settings.');

    // Return raw response for streaming
    return fetch(`${this.baseUrl}/api/v1/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'X-Anthropic-Key': anthropicKey,
      },
      body: JSON.stringify({ message, history }),
    });
  }

  async quickAnalysis(playerName: string): Promise<ApiResponse<string>> {
    return this.fetch('/api/v1/chat/quick', {
      method: 'POST',
      body: JSON.stringify({ player_name: playerName }),
    }, true, true);
  }

  // League Analysis endpoints
  async connectSleeper(username: string): Promise<LeagueConnectResponse> {
    return this.fetch('/api/v1/league/connect', {
      method: 'POST',
      body: JSON.stringify({ sleeper_username: username }),
    });
  }

  async analyzeLeague(leagueId: string, rosterId?: number): Promise<LeagueAnalysis> {
    const params = rosterId ? `?roster_id=${rosterId}` : '';
    return this.fetch(`/api/v1/league/${leagueId}/analysis${params}`);
  }

  async getPowerRankings(leagueId: string): Promise<PowerRanking[]> {
    return this.fetch(`/api/v1/league/${leagueId}/power-rankings`);
  }

  async getRosterAnalysis(leagueId: string, rosterId: number): Promise<RosterAnalysis> {
    return this.fetch(`/api/v1/league/${leagueId}/roster/${rosterId}`);
  }

  async getLeagueTrades(leagueId: string, rosterId?: number): Promise<{
    trade_partners: TradePartner[];
    top_suggestions: TradeSuggestion[];
    buy_low_targets: TradeTarget[];
    sell_high_candidates: LeaguePlayerAnalysis[];
  }> {
    const params = rosterId ? `?roster_id=${rosterId}` : '';
    return this.fetch(`/api/v1/league/${leagueId}/trades${params}`);
  }

  async getDynastyHealth(leagueId: string, rosterId?: number): Promise<DynastyHealthBreakdown> {
    const params = rosterId ? `?roster_id=${rosterId}` : '';
    return this.fetch(`/api/v1/league/${leagueId}/dynasty-health${params}`);
  }

  async getChampionshipOdds(leagueId: string, rosterId?: number): Promise<ChampionshipSimulation> {
    const params = rosterId ? `?roster_id=${rosterId}` : '';
    return this.fetch(`/api/v1/league/${leagueId}/championship-odds${params}`);
  }

  async getLeagueState(leagueId: string): Promise<{
    league: SleeperLeague;
    nfl_state: Record<string, unknown>;
    current_week: number;
    season: string;
  }> {
    return this.fetch(`/api/v1/league/${leagueId}/state`);
  }
}

export const api = new ApiClient();
