// src/pages/Home.js

import { useEffect, useState } from "react";
import StoreSelector from "../components/StoreSelector";
import { fetchStores } from "../api/storeService";
import {
  Flex,
  IconButton,
  Text,
  Box,
  Container
} from "@chakra-ui/react";
import { ArrowBackIcon, ArrowForwardIcon } from "@chakra-ui/icons";
import ForecastChart from "../components/ForecastChart";
import CategoryBreakdownChart from "../components/CategoryBreakdownChart";
import AIInsight from "../components/AIInsight";

const BASE_URL = "http://localhost:5000";

export default function Home() {
  const [storeList, setStoreList] = useState([]);
  const [selectedStore, setSelectedStore] = useState("");
  const [timeline, setTimeline] = useState([]);
  const [history, setHistory] = useState([]);
  const [forecast, setForecast] = useState(null);
  const [summary, setSummary] = useState("");
  const [loadingInsight, setLoadingInsight] = useState(false);

  const graphViews = ["total", "category"];
  const [graphViewIndex, setGraphViewIndex] = useState(0);

  useEffect(() => {
    fetchStores()
      .then((data) => setStoreList(data))
      .catch((err) => console.error("❌ Failed to load stores:", err));
  }, []);

  useEffect(() => {
    if (!selectedStore) return;

    fetch(`${BASE_URL}/api/forecast/${selectedStore}`)
      .then((res) => res.json())
      .then((data) => {
        const historyData = data.history || [];
        const forecastData = data.forecast || null;
        const combinedTimeline = [...historyData, ...(forecastData ? [forecastData] : [])];

        setHistory(historyData);
        setForecast(forecastData);
        setTimeline(combinedTimeline);

        fetchAIInsight(combinedTimeline);
      })
      .catch((err) => console.error("❌ Failed to load forecast:", err));
  }, [selectedStore]);

  const fetchAIInsight = async (timelineData) => {
    setLoadingInsight(true);
    try {
      const res = await fetch(`${BASE_URL}/api/explain_forecast`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timeline: timelineData }),
      });

      const data = await res.json();
      setSummary(data.summary || "No insight available.");
    } catch (err) {
      console.error("❌ AI Insight error:", err);
      setSummary("Failed to fetch AI insight.");
    }
    setLoadingInsight(false);
  };

  const handleGraphViewChange = (direction) => {
    const nextIndex =
      direction === "prev"
        ? (graphViewIndex - 1 + graphViews.length) % graphViews.length
        : (graphViewIndex + 1) % graphViews.length;
    setGraphViewIndex(nextIndex);
    fetchAIInsight(timeline); // Refresh insight when view changes
  };

  const forecastValue = (() => {
    if (!forecast) return null;
    if (Array.isArray(forecast)) return forecast[0]?.sales ?? null; // current API
    // legacy shapes, just in case
    return forecast.sales ?? forecast.Sales ?? null;
  })();

  return (
    <Container maxW="6xl" py={8}>
      <Box mb={6}>
        <StoreSelector
          storeList={storeList}
          selectedStore={selectedStore}
          setSelectedStore={setSelectedStore}
        />
      </Box>

      <Flex justify="center" align="center" mt={4} mb={4}>
        <IconButton
          icon={<ArrowBackIcon />}
          onClick={() => handleGraphViewChange("prev")}
          aria-label="Previous View"
          mr={2}
        />
        <Text fontWeight="bold" fontSize="lg">
          {graphViews[graphViewIndex] === "total"
            ? "Total Sales Forecast"
            : "Category Breakdown"}
        </Text>
        <IconButton
          icon={<ArrowForwardIcon />}
          onClick={() => handleGraphViewChange("next")}
          aria-label="Next View"
          ml={2}
        />
      </Flex>

      <Box
        mb={6}
        p={4}
        borderWidth="1px"
        borderRadius="lg"
        bg="white"
        boxShadow="md"
        textAlign="center"
      >
        <Text fontSize="2xl" fontWeight="bold" color="green.500">
          {forecastValue != null
            ? `$${forecastValue.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}`
            : "--"}
        </Text>

      </Box>

      <Box mb={6}>
        {graphViews[graphViewIndex] === "total" ? (
          <ForecastChart history={history} forecast={forecast} />
        ) : (
          <CategoryBreakdownChart history={history} />
        )}
      </Box>

      <AIInsight summary={summary} loading={loadingInsight} />
    </Container>
  );
}
