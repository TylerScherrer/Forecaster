import { getJSON } from "./base";

export async function fetchStores() {
  const data = await getJSON("/stores");
  if (!Array.isArray(data)) {
    throw new Error("Invalid store list response");
  }
  return data;
}
