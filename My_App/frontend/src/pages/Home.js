// src/pages/Home.js
import { useEffect, useState } from "react";
import StoreSelector from "../components/StoreSelector";
import { fetchStores } from "../api/storeService";
import {
  Box, Container, Flex, IconButton, Text,
  Grid, GridItem, Button, useDisclosure, Drawer, DrawerBody,
  DrawerContent, DrawerHeader, DrawerOverlay
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
  const drawer = useDisclosure();

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
    const next =
      direction === "prev"
        ? (graphViewIndex - 1 + graphViews.length) % graphViews.length
        : (graphViewIndex + 1) % graphViews.length;
    setGraphViewIndex(next);
    fetchAIInsight(timeline);
  };

  return (
    <Container maxW="7xl" py={8}>
      <Grid templateColumns={{ base: "1fr", lg: "2fr 1fr" }} gap={6} alignItems="start">
        {/* LEFT: controls, KPI, charts */}
        <GridItem>
          {/* Store selector */}
          <Box mb={6}>
            <StoreSelector
              storeList={storeList}
              selectedStore={selectedStore}
              setSelectedStore={setSelectedStore}
            />
          </Box>

          {/* KPI banner */}
          <Box
            mb={6}
            p={4}
            borderWidth="1px"
            borderRadius="lg"
            bg="white"
            boxShadow="sm"
            textAlign="center"
          >
            <Text fontWeight="semibold" color="gray.600" mb={1}>
              Total Sales Forecast
            </Text>
            <Text fontSize="2xl" fontWeight="bold" color="green.500">
              {forecast && forecast[0]?.sales !== undefined
                ? `$${Number(forecast[0].sales).toLocaleString(undefined, { minimumFractionDigits: 2 })}`
                : "--"}
            </Text>
          </Box>

          {/* Toggle */}
          <Flex justify="center" align="center" mb={4} gap={2}>
            <IconButton
              icon={<ArrowBackIcon />}
              onClick={() => handleGraphViewChange("prev")}
              aria-label="Previous View"
              size="sm"
            />
            <Text fontWeight="bold" fontSize="lg">
              {graphViews[graphViewIndex] === "total"
                ? "Sales Growth + Forecast"
                : "Category Breakdown"}
            </Text>
            <IconButton
              icon={<ArrowForwardIcon />}
              onClick={() => handleGraphViewChange("next")}
              aria-label="Next View"
              size="sm"
            />
          </Flex>

          {/* Chart */}
          <Box mb={6}>
            {graphViews[graphViewIndex] === "total" ? (
              <ForecastChart history={history} forecast={forecast} />
            ) : (
              <CategoryBreakdownChart history={history} />
            )}
          </Box>
        </GridItem>

        {/* RIGHT: sticky AI panel (hidden on mobile) */}
        <GridItem display={{ base: "none", lg: "block" }}>
          <Box position="sticky" top="80px">
            <AIInsight
              summary={summary}
              loading={loadingInsight}
              boxProps={{ maxH: "75vh", overflowY: "auto" }}
            />
          </Box>
        </GridItem>
      </Grid>

      {/* Mobile FAB to open AI insight as a drawer */}
      <Button
        display={{ base: "inline-flex", lg: "none" }}
        position="fixed"
        right={4}
        bottom={4}
        colorScheme="purple"
        onClick={drawer.onOpen}
      >
        AI Insight
      </Button>

      <Drawer isOpen={drawer.isOpen} placement="right" onClose={drawer.onClose} size="sm">
        <DrawerOverlay />
        <DrawerContent>
          <DrawerHeader>AI Insight</DrawerHeader>
          <DrawerBody>
            <AIInsight summary={summary} loading={loadingInsight} />
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </Container>
  );
}
