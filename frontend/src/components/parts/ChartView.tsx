import { Box, Table, TableBody, TableCell, TableHead, TableRow, Typography } from "@mui/material";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ChartPart } from "../../api/types";

import { CHART_COLORS as COLORS } from "../../app/theme";

/** A bar or line chart plus a "View data" table, so the numbers are readable by screen readers and copyable. */
export default function ChartView({ part }: { part: ChartPart }) {
  const label = part.title ?? "Chart";
  const Chart = part.kind === "line" ? LineChart : BarChart;
  return (
    <Box sx={{ my: 1.5 }}>
      {part.title && (
        <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
          {part.title}
        </Typography>
      )}
      <Box role="img" aria-label={`${part.kind} chart: ${label}`} sx={{ width: "100%", height: 260, minWidth: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <Chart data={part.data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey={part.x} />
            <YAxis width={44} />
            <Tooltip />
            {part.series.length > 1 && <Legend />}
            {part.series.map((s, i) =>
              part.kind === "line" ? (
                <Line key={s.key} type="monotone" connectNulls={false} dataKey={s.key} name={s.label} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={false} />
              ) : (
                <Bar key={s.key} dataKey={s.key} name={s.label} fill={COLORS[i % COLORS.length]} radius={[3, 3, 0, 0]} />
              ),
            )}
          </Chart>
        </ResponsiveContainer>
      </Box>
      <Box component="details" sx={{ mt: 0.5, fontSize: 13, color: "text.secondary" }}>
        <summary>View data</summary>
        <Table size="small" aria-label={`${label} data`}>
          <TableHead>
            <TableRow>
              <TableCell>{part.x}</TableCell>
              {part.series.map((s) => (
                <TableCell key={s.key} align="right">
                  {s.label}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {part.data.map((point, i) => (
              <TableRow key={i}>
                <TableCell>{String(point[part.x])}</TableCell>
                {part.series.map((s) => (
                  <TableCell key={s.key} align="right">
                    {point[s.key] ?? ""}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
    </Box>
  );
}
