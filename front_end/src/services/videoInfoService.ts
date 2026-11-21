import { computed, reactive, watch } from 'vue';

import { getDatabase, VIDEO_INFO_STORE_NAME } from './database';
import { serviceConfig } from './store';

import $axios from '@/http';
import type { MS_Mode, MS_Software } from '@/utils/ms_const';
import { VideoAbstract } from '@/utils/videoabstract';

export interface ParsedVideoInfo {
    id: number;
    software: MS_Software;
    level: string;
    mode: MS_Mode;
    end_time: string | null;
    file_size: number;
    timems: number;
    bv: number | null;
    left: number | null;
    right: number | null;
    double: number | null;
    left_ce: number | null;
    right_ce: number | null;
    double_ce: number | null;
    path: number | null;
    pluck: number | null;
    flag: number | null;
    op: number | null;
    isl: number | null;
    cell0: number | null;
    cell1: number | null;
    cell2: number | null;
    cell3: number | null;
    cell4: number | null;
    cell5: number | null;
    cell6: number | null;
    cell7: number | null;
    cell8: number | null;
    identifier: string;
    tournament_identifier: string[];
}

export interface VideoMetadata {
    id: number;
    ongoing_tournament: boolean;
    player?: number;
    player_id?: number;
    upload_time?: string;
    state?: string;
}

interface VideoInfoReference {
    id: number;
    ongoing_tournament?: boolean;
}

interface CacheRow {
    id: number;
    scope: string;
    data: ParsedVideoInfo;
}

function parsedFields(row: ParsedVideoInfo & { ongoing_tournament: boolean }): ParsedVideoInfo {
    const data = { ...row };
    Reflect.deleteProperty(data, 'ongoing_tournament');
    return data;
}

interface Viewer {
    id: number;
    revision: number;
}

interface PendingRequest {
    row: VideoInfoReference;
    viewer: Viewer;
    promise: Promise<ParsedVideoInfo>;
    resolve: (data: ParsedVideoInfo) => void;
    reject: (error: unknown) => void;
    inFlight: boolean;
}

interface DownloadTask {
    page: string;
    items: Map<string, boolean>;
}

const pending = new Map<string, PendingRequest>();
const downloads = reactive(new Map<symbol, DownloadTask>());
// Public parsed fields and requests are shared across login sessions.
const PUBLIC_VIEWER: Viewer = { id: 0, revision: -1 };
let currentViewer: Viewer = { id: 0, revision: 0 };
let running = false;
let timer: ReturnType<typeof setTimeout> | undefined;
const infoRequests = new Map<string, Promise<ParsedVideoInfo>>();

export const videoInfoDownloads = computed(() => [...downloads.values()]);

function viewer(): Viewer {
    return { ...currentViewer };
}

function sameViewer(value: Viewer): boolean {
    return value === PUBLIC_VIEWER || (value.id === currentViewer.id && value.revision === currentViewer.revision);
}

export function setVideoInfoViewer(id: number, revision: number): void {
    currentViewer = { id, revision };
}

function scope(row: VideoInfoReference, value: Viewer): string {
    return row.ongoing_tournament === false ? 'public' : `user:${value.id}`;
}

function canCache(row: VideoInfoReference, value: Viewer): boolean {
    return row.ongoing_tournament !== true || (value.id > 0 && serviceConfig.value.videoInfoCacheUnpublished);
}

export function videoInfoBatchSize(): number {
    const value = Math.trunc(serviceConfig.value.videoInfoBatchSize);
    return Number.isFinite(value) ? Math.max(1, Math.min(100, value)) : 100;
}

function batchDelay(): number {
    const value = serviceConfig.value.videoInfoBatchDelay;
    return Number.isFinite(value) ? Math.max(250, Math.min(60000, value)) : 250;
}

async function readCached(rows: VideoInfoReference[], value: Viewer): Promise<Map<number, ParsedVideoInfo>> {
    const result = new Map<number, ParsedVideoInfo>();
    try {
        const db = await getDatabase();
        for (let offset = 0; offset < rows.length; offset += 200) {
            const tx = db.transaction(VIDEO_INFO_STORE_NAME);
            const found = await Promise.all(rows.slice(offset, offset + 200).map(async (row) => {
                const candidates = row.ongoing_tournament === undefined ? [{ ...row, ongoing_tournament: false }, { ...row, ongoing_tournament: true }] : [row];
                for (const candidate of candidates) {
                    if (!canCache(candidate, value)) continue;
                    const cached = await tx.store.get([scope(candidate, value), row.id]) as CacheRow | undefined;
                    if (cached !== undefined) return { data: cached.data, unpublished: candidate.ongoing_tournament === true };
                }
                return undefined;
            }));
            await tx.done;
            for (const cached of found) {
                if (cached !== undefined && (!cached.unpublished || sameViewer(value))) result.set(cached.data.id, cached.data);
            }
        }
    } catch {
        // Read failures fall back to the batch API.
    }
    return result;
}

async function writeCached(rows: (ParsedVideoInfo & { ongoing_tournament: boolean })[], value: Viewer): Promise<void> {
    if (rows.length === 0 || !sameViewer(value)) return;
    try {
        const db = await getDatabase();
        const tx = db.transaction(VIDEO_INFO_STORE_NAME, 'readwrite');
        for (const row of rows) {
            if (!sameViewer(value) || !canCache(row, value)) continue;
            await tx.store.put({ id: row.id, scope: scope(row, value), data: parsedFields(row) } satisfies CacheRow);
        }
        await tx.done;
    } catch {
        // A full or disabled database must not discard successful downloads.
    }
}

export async function clearUnpublishedVideoCache(userId = currentViewer.id): Promise<void> {
    if (userId < 1) return;
    try {
        const db = await getDatabase();
        const tx = db.transaction(VIDEO_INFO_STORE_NAME, 'readwrite');
        let cursor = await tx.store.index('scope').openCursor(`user:${userId}`);
        while (cursor) {
            await cursor.delete();
            cursor = await cursor.continue();
        }
        await tx.done;
    } catch {
        // Disabling the policy also prevents reads/writes, even if storage itself is unavailable.
    }
}

watch(() => serviceConfig.value.videoInfoCacheUnpublished, (enabled) => {
    if (!enabled) void clearUnpublishedVideoCache();
}, { flush: 'sync' });

function schedule(): void {
    if (running || timer !== undefined || pending.size === 0) return;
    timer = setTimeout(() => {
        timer = undefined;
        void processBatch();
    }, batchDelay());
}

async function processBatch(): Promise<void> {
    const first = [...pending.values()].find((request) => !request.inFlight);
    if (first === undefined) return;
    const entries = [...pending.entries()].filter(([, request]) => !request.inFlight && request.viewer.id === first.viewer.id && request.viewer.revision === first.viewer.revision).slice(0, videoInfoBatchSize());
    running = true;
    entries.forEach(([, request]) => {
        request.inFlight = true;
    });
    try {
        const { data } = await $axios.get<(ParsedVideoInfo & { ongoing_tournament: boolean })[]>('/api/video/staticdetailbatch', { params: { ids: entries.map(([, request]) => request.row.id).join(',') } });
        await writeCached(data.filter((row) => !row.ongoing_tournament), PUBLIC_VIEWER);
        await writeCached(data.filter((row) => row.ongoing_tournament), first.viewer);
        const found = new Map(data.map((row) => [row.id, row]));
        for (const [, request] of entries) {
            const row = found.get(request.row.id);
            if (row === undefined) request.reject(new Error(`Video ${request.row.id} is missing or unavailable.`));
            else if (row.ongoing_tournament && (request.viewer === PUBLIC_VIEWER || !sameViewer(request.viewer))) request.reject(new Error('Login session changed.'));
            else request.resolve(parsedFields(row));
        }
    } catch (error) {
        entries.forEach(([, request]) => {
            request.reject(error);
        });
    } finally {
        entries.forEach(([key]) => {
            pending.delete(key);
        });
        running = false;
        schedule();
    }
}

function enqueue(row: VideoInfoReference, value: Viewer): Promise<ParsedVideoInfo> {
    const requestViewer = row.ongoing_tournament === false ? PUBLIC_VIEWER : value;
    const key = `${requestViewer.id}:${requestViewer.revision}:${row.id}`;
    const existing = pending.get(key);
    if (existing !== undefined) return existing.promise;
    const deferred = Promise.withResolvers<ParsedVideoInfo>();
    pending.set(key, { ...deferred, row, viewer: requestViewer, inFlight: false });
    schedule();
    return deferred.promise;
}

export async function fetchVideoInfos<Row extends VideoInfoReference>(rows: Row[], onBatch?: (batch: (Row & ParsedVideoInfo)[]) => void): Promise<(Row & ParsedVideoInfo)[]> {
    const value = viewer();
    const unique = [...new Map(rows.map((row) => [row.id, row])).values()];
    if (unique.some((row) => !Number.isSafeInteger(row.id) || row.id < 1)) throw new Error('Invalid server video ID.');
    let taskId: symbol | undefined;
    try {
        const found = await readCached(unique, value);
        const emit = (ids: Set<number>): void => {
            if (onBatch === undefined || ids.size === 0) return;
            const batch: (Row & ParsedVideoInfo)[] = [];
            for (const row of rows) {
                const data = found.get(row.id);
                if (data !== undefined && ids.has(row.id)) batch.push({ ...data, ...row });
            }
            if (batch.length > 0) onBatch(batch);
        };
        emit(new Set(found.keys()));
        const missing = unique.filter((row) => !found.has(row.id));
        if (missing.length > 0) {
            taskId = Symbol('video-download');
            const { hash, pathname, search } = window.location;
            const page = hash?.startsWith('#/') ? hash.slice(1).split('#')[0] : pathname + search;
            downloads.set(taskId, { page, items: new Map(missing.map((row) => [`${scope(row, value)}:${row.id}`, false])) });
        }
        const batchSize = videoInfoBatchSize();
        for (let offset = 0; offset < missing.length; offset += batchSize) {
            const slice = missing.slice(offset, offset + batchSize);
            const settled = await Promise.allSettled(slice.map(async (row) => {
                const data = await enqueue(row, value);
                found.set(row.id, data);
                if (taskId !== undefined) downloads.get(taskId)?.items.set(`${scope(row, value)}:${row.id}`, true);
            }));
            const failure = settled.find((result) => result.status === 'rejected');
            if (failure?.status === 'rejected') throw failure.reason instanceof Error ? failure.reason : new Error(String(failure.reason));
            emit(new Set(slice.filter((row) => found.has(row.id)).map((row) => row.id)));
        }
        if (unique.some((row) => row.ongoing_tournament === true) && !sameViewer(value)) throw new Error('Login session changed.');
        return rows.map((row) => {
            const data = found.get(row.id);
            if (data === undefined) throw new Error(`Video ${row.id} is unavailable.`);
            return { ...data, ...row };
        });
    } finally {
        if (taskId !== undefined) downloads.delete(taskId);
    }
}

/** Read stable fields by ID; the batch response determines their public or user cache scope. */
export function fetchVideoInfo(id: number): Promise<ParsedVideoInfo> {
    if (!Number.isSafeInteger(id) || id < 1) return Promise.reject(new Error('Invalid server video ID.'));
    const value = viewer();
    const key = `${value.id}:${value.revision}:${id}`;
    const existing = infoRequests.get(key);
    if (existing !== undefined) return existing;
    const request = fetchVideoInfos([{ id }]).then(([row]) => row).finally(() => {
        infoRequests.delete(key);
    });
    infoRequests.set(key, request);
    return request;
}

function sum(values: (number | null)[]): number | null {
    return values.some((value) => value === null) ? null : values.reduce<number>((total, value) => total + (value ?? 0), 0);
}

export type VideoDisplayFields = ParsedVideoInfo & Record<'cl' | 'ce' | 'bvs' | 'iqg' | 'left_s' | 'right_s' | 'double_s' | 'cl_s' | 'left_ces' | 'right_ces' | 'double_ces' | 'ce_s' | 'flag_s' | 'ioe' | 'thrp' | 'corr' | 'stnb', number | null>;

/** Restore generated statistics for existing tables/exports without storing duplicate values. */
export function videoDisplayFields(data: ParsedVideoInfo): VideoDisplayFields {
    const cl = sum([data.left, data.right, data.double]);
    const ce = sum([data.left_ce, data.right_ce, data.double_ce]);
    const time = data.timems / 1000;
    const rate = (value: number | null) => (value === null ? null : time === 0 ? 0 : value / time);
    const ratio = (a: number | null, b: number | null) => (a === null || b === null || b === 0 ? null : a / b);
    const video = new VideoAbstract({ ...data, bv: data.bv ?? NaN, cl, ce });
    return {
        ...data,
        cl,
        ce,
        bvs: rate(data.bv),
        iqg: time === 0 ? 0 : data.bv === null ? null : data.bv / time ** 1.7,
        left_s: rate(data.left),
        right_s: rate(data.right),
        double_s: rate(data.double),
        cl_s: rate(cl),
        left_ces: rate(data.left_ce),
        right_ces: rate(data.right_ce),
        double_ces: rate(data.double_ce),
        ce_s: rate(ce),
        flag_s: rate(data.flag),
        ioe: ratio(data.bv, cl),
        thrp: ratio(data.bv, ce),
        corr: ratio(ce, cl),
        stnb: time === 0 ? 0 : Number.isFinite(video.stnb) ? video.stnb : null,
    };
}
