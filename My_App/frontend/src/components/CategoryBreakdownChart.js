import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
} from "recharts";
import { Card, CardBody, Heading } from "@chakra-ui/react";

// Define color palette for the chart
const COLORS = ["#3182CE", "#38B2AC", "#DD6B20", "#E53E3E", "#805AD5", "#319795", "#ECC94B"];


/**
 * CategoryBreakdownChart
 * Props:
 *  - history: Array of records like:
 *      {
 *        date: "YYYY-MM-DD",
 *        total_sales: 12345.67,
 *        categories: { "WHISKEY": 500, "VODKA": 300, ... }
 *      }
 */
export default function CategoryBreakdownChart({ history }) {
  if (!history || history.length === 0) return null;

  // Convert category breakdowns to chart-friendly format
  const chartData = history.map((record) => ({
    date: record.date,
    ...record.categories,
  }));

  const categoryKeys = Object.keys(chartData[0]).filter((key) => key !== "date");

  return (
    <Card boxShadow="lg" p={4} width="100%">
      <CardBody>
        <Heading size="md" mb={3}>Category Breakdown</Heading>
        <ResponsiveContainer width="100%" height={500}>
          <LineChart data={chartData}>
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Legend />
            {categoryKeys.map((key, index) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={COLORS[index % COLORS.length]}
                strokeWidth={2}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardBody>
    </Card>
  );
}
