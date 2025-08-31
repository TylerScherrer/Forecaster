// src/pages/Home.js

/**
 * Home Page
 * ----------
 * UX summary
 * - Loads the store list (cache-first with ETA + background refresh).
 * - When a store is chosen, loads history + forecast and asks the AI for a summary.
 * - Clicking a point on the chart opens a small popup next to the point with a
 *   focused AI explanation (“point-and-explain”). A right-side panel shows the
 *   broader summary.
 *
 * Data contracts
 * - GET  /api/stores                 → store list (array or { stores: [...] })
 * - GET  /api/forecast/:storeId      → { history: [...], forecast: [...] }
 * - POST /api/explain_forecast       → { summary }   (accepts { timeline, focus? })
 */

import { useEffect, useRef, useState } from "react";
import StoreSelector from "../components/StoreSelector";
import { fetchStores } from "../api/storeService";
import {
  Box,
  Container,
  Flex,
  IconButton,
  Text,
  Grid,
  GridItem,
  Button,
  useDisclosure,
  Drawer,
  DrawerBody,
  DrawerContent,
  DrawerHeader,
  DrawerOverlay,
  Alert,
  AlertIcon,
  HStack,
  Progress,
  Spinner,
  useToast,
} from "@chakra-ui/react";
import { ArrowBackIcon, ArrowForwardIcon } from "@chakra-ui/icons";
import ForecastChart from "../components/ForecastChart";
import CategoryBreakdownChart from "../components/CategoryBreakdownChart";
import AIInsight from "../components/AIInsight";

const BASE_URL = "http://localhost:5000";

/* ---------------- Inline loader components (no extra files) ---------------- */

function LoadingStoresCard({ etaMs = 1500, label = "Loading stores…" }) {
  const start = useRef(Date.now());
  const [remaining, setRemaining] = useState(etaMs);

  useEffect(() => {
    start.current = Date.now();
    setRemaining(etaMs);
    const id = setInterval(() => {
      const elapsed = Date.now() - start.current;
      setRemaining(Math.max(0, etaMs - elapsed));
    }, 100);
    return () => clearInterval(id);
  }, [etaMs]);

  const pct = etaMs > 0 ? Math.min(100, ((etaMs - remaining) / etaMs) * 100) : 0;
  const fmt = (ms) => `${Math.max(0, ms / 1000).toFixed(1)}s`;

  return (
    <Box p={4} borderWidth="1px" borderRadius="xl" bg="white" shadow="sm">
      <HStack spacing={3} mb={3}>
        <Spinner size="sm" />
        <Text fontWeight="semibold">
          {label} • ETA: {fmt(remaining)}
        </Text>
      </HStack>
      <Progress value={pct} size="sm" isAnimated hasStripe />
      <Text mt={2} fontSize="sm" color="gray.600">
        Preparing store list. This depends on network speed.
      </Text>
    </Box>
  );
}

function RefreshingBar({ etaMs = 1500 }) {
  const start = useRef(Date.now());
  const [remaining, setRemaining] = useState(etaMs);
  useEffect(() => {
    start.current = Date.now();
    setRemaining(etaMs);
    const id = setInterval(() => {
      const elapsed = Date.now() - start.current;
      setRemaining(Math.max(0, etaMs - elapsed));
    }, 100);
    return () => clearInterval(id);
  }, [etaMs]);
  const pct = etaMs > 0 ? Math.min(100, ((etaMs - remaining) / etaMs) * 100) : 0;
  const fmt = (ms) => `${Math.max(0, ms / 1000).toFixed(1)}s`;
  return (
    <Box mt={2}>
      <HStack spacing={2} mb={1}>
        <Text fontSize="sm" color="gray.700" fontWeight="medium">
          Refreshing store list…
        </Text>
        <Text fontSize="sm" color="gray.600">ETA: {fmt(remaining)}</Text>
      </HStack>
      <Progress value={pct} size="xs" isAnimated hasStripe />
    </Box>
  );
}

/* ---------------- Page component ---------------- */

export default function Home() {
  const toast = useToast();

  /* Focus popup state for the clicked point */
  const [focusPoint, setFocusPoint] = useState(null);     // { date, value, source, cx?, cy? }
  const [focusLoading, setFocusLoading] = useState(false);
  const [focusSummary, setFocusSummary] = useState("");

  /* Stores + selection */
  const [storeList, setStoreList] = useState([]);
  const [selectedStore, setSelectedStore] = useState("");

  /* Timeline data */
  const [timeline, setTimeline] = useState([]);
  const [history, setHistory] = useState([]);
  const [forecast, setForecast] = useState([]);

  /* AI (right panel) */
  const [summary, setSummary] = useState("");
  const [loadingInsight, setLoadingInsight] = useState(false);

  /* Chart view toggle */
  const graphViews = ["total", "category"];
  const [graphViewIndex, setGraphViewIndex] = useState(0);

  /* Mobile drawer for AI panel */
  const drawer = useDisclosure();

  /* Loading UX for stores */
  const [loadingStores, setLoadingStores] = useState(true);
  const [refreshingStores, setRefreshingStores] = useState(false);
  const [storesError, setStoresError] = useState("");
  const usedCacheRef = useRef(false);
  const [etaMs, setEtaMs] = useState(Number(localStorage.getItem("storesLoadEMA")) || 1500);

  const STORES_CACHE_KEY = "storesCache:v3";
  const STORES_CACHE_TTL_MS = 6 * 60 * 60 * 1000;
  const STORES_ETA_KEY = "storesLoadEMA";

  const updateEma = (duration) => {
    const prev = Number(localStorage.getItem(STORES_ETA_KEY)) || 1500;
    const ema = Math.round(prev * 0.7 + duration * 0.3);
    localStorage.setItem(STORES_ETA_KEY, String(ema));
    setEtaMs(ema);
  };

  /* 1) Load store list (cache-first + background refresh) */
  useEffect(() => {
    let cancelled = false;

    const readCacheIfFresh = () => {
      try {
        const raw = localStorage.getItem(STORES_CACHE_KEY);
        if (!raw) return false;
        const { data, ts } = JSON.parse(raw);
        if (!Array.isArray(data) || !ts) return false;
        if (Date.now() - ts < STORES_CACHE_TTL_MS) {
          setStoreList(data);
          setLoadingStores(false);
          usedCacheRef.current = true;
          return true;
        }
      } catch {}
      return false;
    };

    const fetchAndRecord = async (showSpinner) => {
      if (showSpinner) setLoadingStores(true);
      setStoresError("");
      const started = Date.now();
      try {
        const stores = await fetchStores(); // normalized by api/storeService
        const list = Array.isArray(stores) ? stores : (stores?.stores || stores || []);
        if (!cancelled) {
          setStoreList(list);
          localStorage.setItem(STORES_CACHE_KEY, JSON.stringify({ data: list, ts: Date.now() }));
        }
      } catch (e) {
        if (!cancelled) {
          setStoresError(
            usedCacheRef.current
              ? `Refresh failed; showing cached list. (${e?.message || "Network error"})`
              : `Failed to load stores. (${e?.message || "Network error"})`
          );
        }
      } finally {
        const duration = Date.now() - started;
        if (!cancelled) {
          updateEma(duration);
          setLoadingStores(false);
          setRefreshingStores(false);
        }
      }
    };

    const hadCache = readCacheIfFresh();
    setRefreshingStores(hadCache);
    fetchAndRecord(!hadCache);

    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* 2) Load forecast/history + AI when a store is selected */
  useEffect(() => {
    if (!selectedStore) return;

    // clear previous focus highlight when changing stores
    setFocusPoint(null);
    setFocusSummary("");
    setFocusLoading(false);

    const run = async () => {
      try {
        const res = await fetch(`${BASE_URL}/api/forecast/${selectedStore}`);
        const data = await res.json();
        const historyData = Array.isArray(data.history) ? data.history : [];
        const forecastData = Array.isArray(data.forecast)
          ? data.forecast
          : data.forecast
          ? [data.forecast]
          : [];
        const combinedTimeline = [...historyData, ...forecastData];

        setHistory(historyData);
        setForecast(forecastData);
        setTimeline(combinedTimeline);

        await fetchAIInsight(combinedTimeline); // refresh right-panel summary
      } catch (err) {
        console.error("❌ Failed to load forecast:", err);
      }
    };
    run();
  }, [selectedStore]);

  /* Ask AI for the broad summary (right panel).
     If `focus` is passed, the backend will tailor the answer. */
  const fetchAIInsight = async (timelineData, focus = null) => {
    setLoadingInsight(true);
    try {
      const res = await fetch(`${BASE_URL}/api/explain_forecast`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timeline: timelineData, focus }),
      });
      const data = await res.json();
      setSummary(data.summary || "No insight available.");
    } catch (err) {
      console.error("❌ AI Insight error:", err);
      setSummary("Failed to fetch AI insight.");
    } finally {
      setLoadingInsight(false);
    }
  };

  /* Point-and-explain click handler from the chart */
  const handlePointSelect = async (pt) => {
    console.log("[Home] point selected:", pt);
    toast({
      title: "Point selected",
      description: `${new Date(pt.date).toLocaleDateString()} • ${pt.source} • ${pt.value.toLocaleString()}`,
      status: "info",
      duration: 1500,
      isClosable: true,
      position: "bottom-left",
    });

    setFocusPoint(pt);
    setFocusLoading(true);
    setFocusSummary("Analyzing…");
    try {
      const res = await fetch(`${BASE_URL}/api/explain_forecast`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timeline, focus: pt }),
      });
      const data = await res.json();
      setFocusSummary(data.summary || "No insight available.");
    } catch (e) {
      console.error("[Home] focused insight error:", e);
      setFocusSummary("Failed to fetch insight.");
    } finally {
      setFocusLoading(false);
    }
  };

  const handleClosePopup = () => {
    setFocusPoint(null);
    setFocusSummary("");
    setFocusLoading(false);
  };

  const handleGraphViewChange = (direction) => {
    const next =
      direction === "prev"
        ? (graphViewIndex - 1 + graphViews.length) % graphViews.length
        : (graphViewIndex + 1) % graphViews.length;

    setGraphViewIndex(next);
    // keep right-panel AI in sync with current view (optional)
    fetchAIInsight(timeline);
  };

  /* Retry refresh if we were on cache and network failed */
  const retryRefresh = async () => {
    setRefreshingStores(true);
    setStoresError("");
    const started = Date.now();
    try {
      const stores = await fetchStores();
      const list = Array.isArray(stores) ? stores : (stores?.stores || stores || []);
      setStoreList(list);
      localStorage.setItem(STORES_CACHE_KEY, JSON.stringify({ data: list, ts: Date.now() }));
    } catch (e) {
      setStoresError(`Refresh failed; showing cached list. (${e?.message || "Network error"})`);
    } finally {
      const duration = Date.now() - started;
      updateEma(duration);
      setRefreshingStores(false);
    }
  };

  /* ---------------- Render ---------------- */

  return (
    <Container maxW="7xl" py={6}>
      <Grid templateColumns={{ base: "1fr", lg: "2fr 1fr" }} gap={6} alignItems="start">
        {/* LEFT: selector + charts */}
        <GridItem>
          <Box mb={6}>
            {storesError && !usedCacheRef.current ? (
              <Alert status="error" borderRadius="lg" mb={4}>
                <AlertIcon />
                {storesError}
                <Button ml={4} size="sm" onClick={() => window.location.reload()}>
                  Retry
                </Button>
              </Alert>
            ) : loadingStores ? (
              <LoadingStoresCard etaMs={etaMs} />
            ) : storeList.length === 0 ? (
              <Alert status="warning" borderRadius="lg">
                <AlertIcon />
                No stores were returned by the server.
              </Alert>
            ) : (
              <>
                <StoreSelector
                  storeList={storeList}
                  selectedStore={selectedStore}
                  setSelectedStore={setSelectedStore}
                />

                {storesError && usedCacheRef.current && (
                  <HStack mt={2} spacing={3}>
                    <Text fontSize="sm" color="orange.700">{storesError}</Text>
                    <Button size="xs" onClick={retryRefresh}>Retry refresh</Button>
                  </HStack>
                )}

                {refreshingStores && <RefreshingBar etaMs={etaMs} />}
              </>
            )}
          </Box>

          {/* Chart toggle */}
          <Flex justify="center" align="center" mb={3} gap={2}>
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

          {/* Chart area – single ForecastChart (no duplicates) */}
          <Box maxW="800px" mx="auto" position="relative" zIndex={0}>
            {graphViews[graphViewIndex] === "total" ? (
              <>
                {/* Debug helper: force-select first point */}
                {timeline.length > 0 && (
                  <Button
                    size="xs"
                    variant="outline"
                    mb={2}
                    onClick={() =>
                      handlePointSelect({
                        date: timeline[0].date,
                        value:
                          timeline[0].total ??
                          timeline[0].total_sales ??
                          timeline[0].sales ??
                          timeline[0].value ??
                          0,
                        source: timeline[0].source || "history",
                        cx: 100,
                        cy: 100,
                      })
                    }
                  >
                    Debug: select first point
                  </Button>
                )}

                <ForecastChart
                  history={history}
                  forecast={forecast}
                  height={360}
                  onPointSelect={handlePointSelect}
                  focusPoint={focusPoint}
                  focusSummary={focusSummary}
                  focusLoading={focusLoading}
                  onClosePopup={handleClosePopup}
                />
              </>
            ) : (
              <CategoryBreakdownChart history={history} />
            )}
          </Box>
        </GridItem>

        {/* RIGHT: sticky AI panel */}
        <GridItem display={{ base: "none", lg: "block" }}>
          <Box w="720px" position="sticky" top="80px">
            <AIInsight
              summary={summary}
              loading={loadingInsight}
              boxProps={{ maxH: "90vh", overflowY: "auto" }}
            />
          </Box>
        </GridItem>
      </Grid>

      {/* Mobile AI Drawer */}
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
