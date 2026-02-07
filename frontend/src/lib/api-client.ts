import { API_BASE } from "./constants";
import type {
  BlockWithPredictions,
  District,
  ModelComparison,
  NewsSummary,
  PersonaSummary,
  Prediction,
  PredictionHistory,
  PredictionSummary,
  PrefectureMapData,
  YouTubeSummary,
} from "@/types";

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    next: { revalidate: 1200 },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export async function fetchPredictionSummary(): Promise<PredictionSummary> {
  return fetchJSON("/predictions/summary");
}

export async function fetchLatestPredictions(): Promise<Prediction[]> {
  return fetchJSON("/predictions/latest");
}

export async function fetchDistrictPrediction(id: string): Promise<Prediction> {
  return fetchJSON(`/predictions/district/${id}`);
}

export async function fetchDistrictHistory(id: string): Promise<PredictionHistory[]> {
  return fetchJSON(`/predictions/district/${id}/history`);
}

export async function fetchBattleground(): Promise<Prediction[]> {
  return fetchJSON("/predictions/battleground");
}

export async function fetchDistricts(): Promise<District[]> {
  return fetchJSON("/districts");
}

export async function fetchDistrictDetail(id: string): Promise<District> {
  return fetchJSON(`/districts/${id}`);
}

export async function fetchProportionalBlocks(): Promise<BlockWithPredictions[]> {
  return fetchJSON("/proportional/blocks");
}

export async function fetchPrompts(): Promise<Record<string, unknown>> {
  return fetchJSON("/prompts");
}

export async function fetchYouTubeSummary(): Promise<YouTubeSummary> {
  return fetchJSON("/youtube/summary");
}

export async function fetchNewsSummary(): Promise<NewsSummary> {
  return fetchJSON("/news/summary");
}

export async function fetchModelComparison(): Promise<ModelComparison> {
  return fetchJSON("/news/model-comparison");
}

export async function fetchPersonaSummary(): Promise<PersonaSummary> {
  return fetchJSON("/personas/summary");
}

export async function fetchMapSummary(): Promise<PrefectureMapData[]> {
  return fetchJSON("/districts/map-summary");
}
