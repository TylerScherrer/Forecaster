// src/components/ForecastChart.js
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
} from "recharts";

export default function ForecastChart({ history = [], forecast = [], height = 380 }) {
  const historyArr = Array.isArray(history) ? history : [];
  const forecastArr = Array.isArray(forecast) ? forecast : forecast ? [forecast] : [];

  const combined = [
    ...historyArr.map((h) => ({
      date: h.date,
      value: h.total_sales,
      type: "actual",
    })),
    ...forecastArr.map((f) => ({
      date: f.date,
      value: f.sales,
      type: "forecast",
    })),
  ];

  const lastForecast = forecastArr[forecastArr.length - 1];

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={combined} margin={{ top: 10, right: 16, left: 0, bottom: 0 }}>
        <XAxis dataKey="date" />
        <YAxis />
        <Tooltip />
        <Line
          type="monotone"
          dataKey="value"
          dot={false}
          strokeWidth={2}
          isAnimationActive={false}
        />
        {lastForecast ? (
          <ReferenceDot
            x={lastForecast.date}
            y={lastForecast.sales}
            r={5}
            label={{ value: "Pred", position: "top" }}
          />
        ) : null}
      </LineChart>
    </ResponsiveContainer>
  );
}
