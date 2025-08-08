import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
} from "recharts";
import { Card, CardBody, Heading } from "@chakra-ui/react";

export default function ForecastChart({ history = [], forecast = [] }) {
  if (history.length === 0) return null;

  const combinedData = [
    ...history.map((item) => ({ date: item.date, sales: item.total_sales })),
    ...forecast.map((item) => ({ date: item.date, sales: item.sales })),
  ];

  return (
    <Card boxShadow="lg" p={4} width="100%">
      <CardBody>
        <Heading size="md" mb={3}>
          Sales Growth + Forecast
        </Heading>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={combinedData}>
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="sales"
              stroke="#270cc0ff"
              dot={false}
              isAnimationActive={false}
            />
            {forecast.map((point, idx) => (
              <ReferenceDot
                key={idx}
                x={point.date}
                y={point.sales}
                r={6}
                fill="#38B2AC"
                stroke="#2C7A7B"
                label={{ value: "Predicted", position: "top" }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardBody>
    </Card>
  );
}
