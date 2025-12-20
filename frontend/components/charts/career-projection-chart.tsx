"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  CartesianGrid,
} from "recharts";

interface CareerProjection {
  year: number;
  age: number;
  projected_ktc: number;
  projected_ppg: number | null;
}

interface CareerProjectionChartProps {
  projections: CareerProjection[];
  position: string;
}

// Format KTC value for axis (e.g., 8500 -> "8.5K")
function formatKTC(value: number): string {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}K`;
  }
  return value.toString();
}

// Custom tooltip component
interface TooltipPayloadItem {
  value: number;
  dataKey: string;
  color: string;
  payload: CareerProjection & { label: string };
}

function CustomTooltip({ active, payload }: {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
}) {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0]?.payload;

  return (
    <div className="bg-card border border-border rounded-lg shadow-lg p-3 text-sm">
      <p className="font-medium mb-2">{data.label}</p>
      <div className="space-y-1">
        <p className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-amber-500" />
          <span className="text-muted-foreground">KTC:</span>
          <span className="font-mono font-medium">{data.projected_ktc.toLocaleString()}</span>
        </p>
        {data.projected_ppg !== null && (
          <p className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-emerald-500" />
            <span className="text-muted-foreground">PPG:</span>
            <span className="font-mono font-medium">{data.projected_ppg.toFixed(1)}</span>
          </p>
        )}
      </div>
    </div>
  );
}

export function CareerProjectionChart({ projections, position }: CareerProjectionChartProps) {
  if (!projections || projections.length === 0) {
    return null;
  }

  // Transform data for chart with formatted labels
  const chartData = projections.map((p) => ({
    ...p,
    label: `Year ${p.year} (Age ${p.age})`,
    displayYear: `Yr ${p.year}`,
  }));

  // Check if we have PPG data
  const hasPPGData = projections.some((p) => p.projected_ppg !== null);

  // Calculate Y-axis domains
  const ktcValues = projections.map((p) => p.projected_ktc);
  const maxKTC = Math.max(...ktcValues);
  const minKTC = Math.min(...ktcValues);
  const ktcPadding = (maxKTC - minKTC) * 0.1;

  const ppgValues = projections.filter((p) => p.projected_ppg !== null).map((p) => p.projected_ppg!);
  const maxPPG = ppgValues.length > 0 ? Math.max(...ppgValues) : 20;
  const minPPG = ppgValues.length > 0 ? Math.min(...ppgValues) : 0;

  return (
    <div className="w-full">
      <ResponsiveContainer width="100%" height={220}>
        <LineChart
          data={chartData}
          margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />

          <XAxis
            dataKey="displayYear"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
          />

          {/* Left Y-axis for KTC */}
          <YAxis
            yAxisId="ktc"
            orientation="left"
            domain={[Math.max(0, minKTC - ktcPadding), maxKTC + ktcPadding]}
            tickFormatter={formatKTC}
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            tickLine={false}
            axisLine={{ stroke: "hsl(var(--border))" }}
            width={45}
          />

          {/* Right Y-axis for PPG */}
          {hasPPGData && (
            <YAxis
              yAxisId="ppg"
              orientation="right"
              domain={[Math.max(0, minPPG - 2), maxPPG + 2]}
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
              tickLine={false}
              axisLine={{ stroke: "hsl(var(--border))" }}
              width={35}
            />
          )}

          <Tooltip content={<CustomTooltip />} />

          <Legend
            wrapperStyle={{ paddingTop: 10 }}
            formatter={(value: string) => (
              <span className="text-xs text-muted-foreground">{value}</span>
            )}
          />

          {/* KTC Line - Gold/Amber */}
          <Line
            yAxisId="ktc"
            type="monotone"
            dataKey="projected_ktc"
            name="KTC Value"
            stroke="hsl(43, 74%, 49%)"
            strokeWidth={2}
            dot={{ fill: "hsl(43, 74%, 49%)", strokeWidth: 0, r: 4 }}
            activeDot={{ r: 6, fill: "hsl(43, 74%, 49%)" }}
          />

          {/* PPG Line - Emerald */}
          {hasPPGData && (
            <Line
              yAxisId="ppg"
              type="monotone"
              dataKey="projected_ppg"
              name="Fantasy PPG"
              stroke="hsl(152, 69%, 40%)"
              strokeWidth={2}
              dot={{ fill: "hsl(152, 69%, 40%)", strokeWidth: 0, r: 4 }}
              activeDot={{ r: 6, fill: "hsl(152, 69%, 40%)" }}
            />
          )}
        </LineChart>
      </ResponsiveContainer>

      {/* Age labels below chart */}
      <div className="flex justify-between px-12 mt-1">
        {chartData.map((d, i) => (
          <span key={i} className="text-[10px] text-muted-foreground">
            {d.age}
          </span>
        ))}
      </div>
    </div>
  );
}
