// src/components/AIInsight.js
import React from "react";
import { Box, Text, Spinner } from "@chakra-ui/react";

export default function AIInsight({ summary, loading, boxProps = {} }) {
  return (
    <Box mt={4} p={4} borderWidth="1px" borderRadius="lg" bg="gray.50" {...boxProps}>
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
