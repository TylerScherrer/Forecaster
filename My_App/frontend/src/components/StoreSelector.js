// frontend/src/components/StoreSelector.js

import {
  Button,
  Card,
  CardBody,
  Flex,
  Heading,
  Select,
  Text,
} from "@chakra-ui/react";
import { useEffect, useState } from "react";
import ForecastCard from "./ForecastCard";
import ForecastChart from "./ForecastChart";

export default function StoreSelector({
  storeList,
  selectedStore,
  setSelectedStore,
  history,
  forecast,
}) {
  const [selectedForecast, setSelectedForecast] = useState(null);

  useEffect(() => {
    const selected = storeList.find((s) => s.value === selectedStore);
    setSelectedForecast(selected?.forecast || null);
  }, [selectedStore, storeList]);

  return (
    <Flex direction="row" justify="flex-start" align="flex-start" p={6} gap={12}>
      {/* Store Picker */}
      <Card maxW="850px" mx="-250" width="300px" boxShadow="md" p={4}>
        <CardBody>
          <Heading size="md" mb={4}>Select a Store</Heading>
          <Select
            placeholder="Choose a store"
            value={selectedStore}
            onChange={(e) => setSelectedStore(Number(e.target.value))}
            mb={3}
          >
            {storeList.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </Select>

          {selectedStore && (
            <Text fontSize="sm">
              You selected store <Text as="span" fontWeight="bold">{selectedStore}</Text>
            </Text>
          )}

          <Button mt={4} colorScheme="blue" width="100%">
            Continue
          </Button>
        </CardBody>
      </Card>

      {/* Forecast Summary Card */}
      {selectedForecast !== null && <ForecastCard forecast={selectedForecast} />}

      {/* Forecast Trend Chart */}
      {history?.length > 0 && forecast !== null && (
  <ForecastChart history={history} forecast={forecast} />
)}


    </Flex>
  );
}
