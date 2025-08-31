/**
 * LoadingStores.js
 * -----------------------------------------------------------------------------
 * PURPOSE
 *   Blocking loading card with a live ETA countdown and progress bar shown
 *   while the store list is loading for the first time (no cache yet).
 *
 * PROPS
 *   - etaMs?: number   Estimated total duration in ms (used for countdown)
 *   - label?: string   Optional title, defaults to "Loading stores…"
 */

import { useEffect, useRef, useState } from "react";
import { Box, HStack, Spinner, Text, Progress } from "@chakra-ui/react";

const fmt = (ms) => `${Math.max(0, ms / 1000).toFixed(1)}s`;

export default function LoadingStores({ etaMs = 1500, label = "Loading stores…" }) {
  const start = useRef(Date.now());
  const [remaining, setRemaining] = useState(etaMs);

  useEffect(() => {
    start.current = Date.now();
    setRemaining(etaMs);
    const id = setInterval(() => {
      const elapsed = Date.now() - start.current;
      setRemaining(Math.max(0, etaMs - elapsed));
    }, 100); // smooth updates
    return () => clearInterval(id);
  }, [etaMs]);

  const pct = etaMs > 0 ? Math.min(100, ((etaMs - remaining) / etaMs) * 100) : 0;

  return (
    <Box p={4} borderWidth="1px" borderRadius="xl" bg="white" shadow="sm">
      <HStack spacing={3} mb={3}>
        <Spinner size="sm" />
        <Text fontWeight="semibold">
          {label} ETA: {fmt(remaining)}
        </Text>
      </HStack>
      <Progress value={pct} size="sm" isAnimated hasStripe />
      <Text mt={2} fontSize="sm" color="gray.600">
        Preparing store list. This varies with network speed.
      </Text>
    </Box>
  );
}
