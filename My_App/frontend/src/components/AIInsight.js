// src/components/AIInsight.js

import { Box, Text, Spinner } from "@chakra-ui/react";

function AIInsight({ summary, loading }) {
  return (
    <Box mt={4} p={4} borderWidth="1px" borderRadius="lg" bg="gray.50">
      <Text fontWeight="bold" mb={2}>AI Insight:</Text>
      {loading ? (
        <Spinner size="sm" />
      ) : (
        <Text whiteSpace="pre-wrap">{summary || "No insight yet."}</Text>
      )}
    </Box>
  );
}

export default AIInsight;
