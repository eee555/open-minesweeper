import { reactive } from 'vue';

import { fetchNFIOERecord } from './nfIOERankingService';
import { fetchPathRecord } from './pathRankingService';
import { fetchSaoleiRecords } from './saoleiRankingService';
import { fetchStrictNgRecords } from './strictNgRankingService';
import { fetchThrpRecord } from './thrpRankingService';
import { fetchTPERecord } from './tpeRankingService';

// Revisions invalidate page data without starting background video downloads.
const revisions = reactive(new Map<number, number>());
const saoleiRecords = new Map<number, ReturnType<typeof fetchSaoleiRecords>>();
const strictNgRecords = new Map<number, ReturnType<typeof fetchStrictNgRecords>>();
const thrpRecords = new Map<number, ReturnType<typeof fetchThrpRecord>>();
const tpeRecords = new Map<number, ReturnType<typeof fetchTPERecord>>();
const pathRecords = new Map<number, ReturnType<typeof fetchPathRecord>>();
const nfIOERecords = new Map<number, ReturnType<typeof fetchNFIOERecord>>();

export function profileDataRevision(playerId: number): number {
    return revisions.get(playerId) ?? 0;
}

export function invalidateProfileData(playerId: number): void {
    saoleiRecords.delete(playerId);
    strictNgRecords.delete(playerId);
    thrpRecords.delete(playerId);
    tpeRecords.delete(playerId);
    pathRecords.delete(playerId);
    nfIOERecords.delete(playerId);
    revisions.set(playerId, profileDataRevision(playerId) + 1);
}

export function fetchProfileSaoleiRecords(playerId: number): ReturnType<typeof fetchSaoleiRecords> {
    const existing = saoleiRecords.get(playerId);
    if (existing) return existing;
    const request = fetchSaoleiRecords(playerId).catch((error: unknown) => {
        if (saoleiRecords.get(playerId) === request) saoleiRecords.delete(playerId);
        throw error;
    });
    saoleiRecords.set(playerId, request);
    return request;
}

export function fetchProfileStrictNgRecords(playerId: number): ReturnType<typeof fetchStrictNgRecords> {
    const existing = strictNgRecords.get(playerId);
    if (existing) return existing;
    const request = fetchStrictNgRecords(playerId).catch((error: unknown) => {
        if (strictNgRecords.get(playerId) === request) strictNgRecords.delete(playerId);
        throw error;
    });
    strictNgRecords.set(playerId, request);
    return request;
}

export function fetchProfileThrpRecord(playerId: number): ReturnType<typeof fetchThrpRecord> {
    const existing = thrpRecords.get(playerId);
    if (existing) return existing;
    const request = fetchThrpRecord(playerId).catch((error: unknown) => {
        if (thrpRecords.get(playerId) === request) thrpRecords.delete(playerId);
        throw error;
    });
    thrpRecords.set(playerId, request);
    return request;
}

export function fetchProfileTPERecord(playerId: number): ReturnType<typeof fetchTPERecord> {
    const existing = tpeRecords.get(playerId);
    if (existing) return existing;
    const request = fetchTPERecord(playerId).catch((error: unknown) => {
        if (tpeRecords.get(playerId) === request) tpeRecords.delete(playerId);
        throw error;
    });
    tpeRecords.set(playerId, request);
    return request;
}

export function fetchProfilePathRecord(playerId: number): ReturnType<typeof fetchPathRecord> {
    const existing = pathRecords.get(playerId);
    if (existing) return existing;
    const request = fetchPathRecord(playerId).catch((error: unknown) => {
        if (pathRecords.get(playerId) === request) pathRecords.delete(playerId);
        throw error;
    });
    pathRecords.set(playerId, request);
    return request;
}

export function fetchProfileNFIOERecord(playerId: number): ReturnType<typeof fetchNFIOERecord> {
    const existing = nfIOERecords.get(playerId);
    if (existing) return existing;
    const request = fetchNFIOERecord(playerId).catch((error: unknown) => {
        if (nfIOERecords.get(playerId) === request) nfIOERecords.delete(playerId);
        throw error;
    });
    nfIOERecords.set(playerId, request);
    return request;
}
