import { refreshPlayerMedals } from './medalService';

import $axios from '@/http';
import type { MedalDirection } from '@/utils/medal_const';
import { MedalKind } from '@/utils/medal_const';

export type MedalOverrideMode = 'grant' | 'revoke' | 'auto';

export interface StaffMedalDefinition {
    code: string;
    series: string;
    subseries: string;
    kind: string;
    metric: string;
    direction: MedalDirection;
    level: string;
    style: string;
    thresholds: number[];
    active: boolean;
    hidden: boolean;
}

export interface StaffMedalGrant {
    id: number;
    definition_code: string;
    scope_key: string;
    stage: number;
    granted_at: string;
    revoked_at: string | null;
    revoke_reason: string;
}

export interface StaffMedalOverride {
    id: number;
    definition_code: string;
    scope_key: string;
    mode: 'grant' | 'revoke';
    stage: number | null;
    reason: string;
    actor_id: number | null;
    updated_at: string;
}

export interface StaffMedalHistory {
    id: number;
    definition_code: string;
    scope_key: string;
    action: MedalOverrideMode;
    stage: number | null;
    reason: string;
    actor_id: number | null;
    created_at: string;
}

export interface StaffPlayerMedals {
    user_id: number;
    username: string;
    grants: StaffMedalGrant[];
    overrides: StaffMedalOverride[];
    history: StaffMedalHistory[];
}

export interface MedalOverrideInput {
    user_id: number;
    code: string;
    scope_key: string;
    mode: MedalOverrideMode;
    reason: string;
    stage?: number;
    granted_on?: string;
}

export interface MedalOverrideResult {
    grant_id: number | null;
    mode: MedalOverrideMode;
    enqueued: boolean;
}

export function staffMedalStages(definition: StaffMedalDefinition): number[] {
    return definition.thresholds.length ? definition.thresholds : definition.kind === MedalKind.MANUAL ? [1] : [];
}

const scopedMedalKinds = new Set<string>([MedalKind.MANUAL, MedalKind.EVENT_PLACE, MedalKind.GSC_STAT, MedalKind.GSC_PLACE]);

export function staffMedalAllowsScope(definition: StaffMedalDefinition): boolean {
    return scopedMedalKinds.has(definition.kind);
}

export function validMedalOverride(input: MedalOverrideInput, definition: StaffMedalDefinition | undefined, hasOverride: boolean): boolean {
    if (!Number.isSafeInteger(input.user_id) || input.user_id < 1 || !input.code || !input.reason.trim()) return false;
    if (input.mode === 'auto') return hasOverride;
    if (!definition) return false;
    if (input.scope_key && !staffMedalAllowsScope(definition)) return false;
    if (input.mode === 'revoke') return true;
    if (!definition.active || input.stage === undefined || !staffMedalStages(definition).includes(input.stage)) return false;
    const date = input.granted_on ?? '';
    if (!(/^\d{4}-\d{2}-\d{2}$/).test(date)) return false;
    const parsed = new Date(`${date}T00:00:00Z`);
    return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === date;
}

export async function fetchStaffMedalCatalog(): Promise<StaffMedalDefinition[]> {
    const { data } = await $axios.get<StaffMedalDefinition[]>('/api/medal/staff/catalog');
    return data;
}

export async function fetchStaffPlayerMedals(userId: number): Promise<StaffPlayerMedals> {
    const { data } = await $axios.get<StaffPlayerMedals>(`/api/medal/staff/players/${userId}`);
    return data;
}

export async function setMedalOverride(input: MedalOverrideInput): Promise<MedalOverrideResult> {
    // Match the existing medal API's cookie-compatible Content-Type handling.
    const { data } = await $axios.post<MedalOverrideResult>('/api/medal/staff/overrides', JSON.stringify(input));
    refreshPlayerMedals(input.user_id);
    return data;
}
