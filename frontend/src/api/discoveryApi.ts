/**
 * Functions for each /api/discovery endpoint.
 *
 * One function per backend endpoint. All screening, analysis, and ranking lives
 * in the backend service — these wrappers only shape the request and type the
 * response.
 */

import { get } from './client'
import { buildDiscoveryQuery } from '../lib/discovery'
import type {
  DiscoveryModeInfo,
  DiscoveryQuery,
  DiscoveryRun,
  DiscoveryUniverseInfo,
} from '../types/discovery'

/** GET /api/discovery/modes — supported modes and how each one ranks. */
export async function listDiscoveryModes(): Promise<DiscoveryModeInfo[]> {
  return get<DiscoveryModeInfo[]>('/api/discovery/modes')
}

/** GET /api/discovery/universes — registered stock universes. */
export async function listDiscoveryUniverses(): Promise<DiscoveryUniverseInfo[]> {
  return get<DiscoveryUniverseInfo[]>('/api/discovery/universes')
}

/**
 * GET /api/discovery — run a bounded discovery scan.
 *
 * The run is synchronous and can take a while: it pre-screens the universe and
 * then runs the full analysis pipeline on the shortlist.
 */
export async function runDiscovery(query: DiscoveryQuery): Promise<DiscoveryRun> {
  return get<DiscoveryRun>(`/api/discovery?${buildDiscoveryQuery(query)}`)
}
