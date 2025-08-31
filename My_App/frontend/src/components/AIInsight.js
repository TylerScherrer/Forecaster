import React from "react";
import { Box, Text, Spinner } from "@chakra-ui/react";


// A small presentational component that shows an "AI Insight" card.
// Props:
//   - summary: string | undefined  → the text to display
//   - loading: boolean             → whether we’re still fetching the summary
//   - boxProps: object             → optional extra props for the outer Box (e.g. w, bg, borderColor)
export default function AIInsight({ summary, loading, boxProps = {} }) {
  return (
    <Box maxW="750px" mx="50" mt={4} p={4} borderWidth="1px" borderRadius="lg" bg="gray.50" {...boxProps}>
      <Text fontWeight="bold" mb={2}>
         AI Insight:
      </Text>
      {loading ? (
        <Spinner size="sm" />
      ) : (
        <Text whiteSpace="pre-wrap">{summary || "No insight yet."}</Text>
      )}
    </Box>
  );
}
