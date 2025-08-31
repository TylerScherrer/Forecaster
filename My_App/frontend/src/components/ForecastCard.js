// frontend/src/components/ForecastCard.js

import { Card, CardBody, Heading, Text } from "@chakra-ui/react";

export default function ForecastCard({ forecast }) {
  return (
    <Card  maxW="450px" mx="200" boxShadow="lg" p={4} width="300px" bg="gray.50">
      <CardBody>
        <Heading size="md" mb={3}>
          Forecast
        </Heading>
        <Text fontSize="2xl" color="teal.500" fontWeight="bold">
          ${forecast.toLocaleString()}
        </Text>
        <Text fontSize="sm" color="gray.600" mt={2}>
          Total sales prediction
        </Text>
      </CardBody>
    </Card>
  );
}
