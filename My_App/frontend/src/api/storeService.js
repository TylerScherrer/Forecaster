// src/api/storeService.js

export async function fetchStores() {
  const res = await fetch("http://localhost:5000/api/stores");
  const data = await res.json();

  if (!Array.isArray(data)) {
    throw new Error("Invalid store list response");
  }

  return data;
}
