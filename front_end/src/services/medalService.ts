
import { shallowReactive } from 'vue';

import { serviceConfig } from './store';

import $axios from '@/http';
import en from '@/i18n/locales/en';
import zhCn from '@/i18n/locales/zh-cn';
import { MedalSeries } from '@/utils/medal_const';
import type { MedalDirection } from '@/utils/medal_const';

export interface MedalItem {
    code: string;
    series: string;
    subseries: string;
    kind: string;
    stage: number | null;
    stage_count: number;
    direction: MedalDirection;
    current_value: number | null;
    next_threshold: number | null;
    granted_at: string | null;
    video_id: number | null;
    tournament_id: number | null;
    rank: number | null;
    hidden: boolean;
    annotation: string;
    score: number;
    grant_id: number | null;
    scope_key: string;
    thresholds: number[];
}

export interface PlayerMedals {
    scan_pending: boolean;
    score: number;
    max_pins: number;
    pin_ids: number[];
    pins: MedalItem[];
    series: { series: string; items: MedalItem[] }[];
}

// 名字悬停用的已入档短记录。timestamp 是 Unix 秒，未记录时为 null。GET /api/medal/players/state 返回 PlayerMedalState[]。
export interface MedalStateRecord {
    code: string;
    stage: number;
    timestamp: number | null;
    scope: string;
    tournament: number | null;
    rank: number | null;
}

export interface PlayerMedalState {
    user_id: number;
    grants: MedalStateRecord[];
}

const SUMMARY_TTL = 30_000;
const SCAN_POLL_INTERVAL = 2000;
const SCAN_POLL_LIMIT = 10;
const SUMMARY_CACHE_LIMIT = 50;

// Upload-triggered only: at most eight small status requests, then one summary refresh.
const UPLOAD_SYNC_DELAYS = [1000, 2000, 3000, 5000, 8000, 13000, 20000, 30000];
let uploadSync: { generation: number; attempts: number } | undefined;

export function syncMedalsAfterUpload(): void {
    if (uploadSync) {
        uploadSync.generation += 1;
        return;
    }
    const sync = { generation: 0, attempts: 0 };
    uploadSync = sync;
    const schedule = () => {
        if (sync.attempts >= UPLOAD_SYNC_DELAYS.length) {
            uploadSync = undefined;
            return;
        }
        setTimeout(() => {
            void check();
        }, UPLOAD_SYNC_DELAYS[sync.attempts]);
    };
    const check = async () => {
        const { generation } = sync;
        sync.attempts += 1;
        try {
            const { data } = await $axios.get<{ user_id: number; pending: boolean }>('/api/medal/refresh-status', { timeout: 5000 });
            if (generation !== sync.generation || data.pending) {
                schedule();
                return;
            }
            refreshPlayerMedals(data.user_id);
            uploadSync = undefined;
        } catch {
            // Authentication, rate-limit and network failures must not create a retry loop.
            uploadSync = undefined;
        }
    };
    schedule();
}

interface SummaryListener {
    receive: (summary: PlayerMedals) => void;
    failed: () => void;
}

interface SummaryEntry {
    data?: PlayerMedals;
    expires: number;
    version: number;
    inflight?: Promise<PlayerMedals>;
    listeners: Set<SummaryListener>;
    timer?: ReturnType<typeof setTimeout>;
    polls: number;
}

const summaries = new Map<number, SummaryEntry>();

function entryFor(userId: number): SummaryEntry {
    const existing = summaries.get(userId);
    if (existing) return existing;
    for (const [id, entry] of summaries) {
        if (summaries.size < SUMMARY_CACHE_LIMIT) break;
        if (!entry.listeners.size && !entry.inflight) summaries.delete(id);
    }
    const entry: SummaryEntry = { expires: 0, version: 0, listeners: new Set(), polls: 0 };
    summaries.set(userId, entry);
    return entry;
}

function stopPolling(entry: SummaryEntry) {
    if (entry.timer !== undefined) clearTimeout(entry.timer);
    entry.timer = undefined;
}

function pollPendingScan(userId: number, entry: SummaryEntry) {
    if (entry.data?.scan_pending !== true || !entry.listeners.size || entry.timer !== undefined || entry.polls >= SCAN_POLL_LIMIT) return;
    entry.timer = setTimeout(() => {
        entry.timer = undefined;
        entry.polls += 1;
        void fetchPlayerMedals(userId, true).catch(() => undefined);
    }, SCAN_POLL_INTERVAL);
}

export function fetchPlayerMedals(userId: number, refresh = false): Promise<PlayerMedals> {
    const entry = entryFor(userId);
    if (entry.inflight) return entry.inflight;
    if (!refresh && entry.data && entry.expires > Date.now()) return Promise.resolve(entry.data);
    const { version } = entry;
    const request = $axios.get<PlayerMedals>(`/api/medal/players/${userId}`).then(({ data }) => {
        if (entry.version === version) {
            entry.data = data;
            entry.expires = Date.now() + SUMMARY_TTL;
            if (!data.scan_pending) stopPolling(entry);
            entry.listeners.forEach((listener) => {
                listener.receive(data);
            });
        }
        return data;
    }).catch((error: unknown) => {
        if (entry.version === version) entry.listeners.forEach((listener) => {
            listener.failed();
        });
        throw error;
    }).finally(() => {
        if (entry.inflight === request) {
            entry.inflight = undefined;
            pollPendingScan(userId, entry);
        }
    });
    entry.inflight = request;
    return request;
}

// One request and one bounded scan poller per player, shared by the sidebar and medal page.
export function subscribePlayerMedals(userId: number, receive: SummaryListener['receive'], failed: SummaryListener['failed']): () => void {
    const entry = entryFor(userId);
    if (!entry.listeners.size) entry.polls = 0;
    const listener = { receive, failed };
    entry.listeners.add(listener);
    if (entry.data && entry.expires > Date.now()) {
        receive(entry.data);
        pollPendingScan(userId, entry);
    } else {
        void fetchPlayerMedals(userId).catch(() => undefined);
    }
    return () => {
        entry.listeners.delete(listener);
        if (!entry.listeners.size) stopPolling(entry);
    };
}

export function refreshPlayerMedals(userId: number): void {
    invalidatePlayerMedalState(userId);
    const entry = entryFor(userId);
    stopPolling(entry);
    entry.version += 1;
    entry.expires = 0;
    entry.inflight = undefined;
    entry.polls = 0;
    if (entry.listeners.size) void fetchPlayerMedals(userId, true).catch(() => undefined);
}

export async function saveMedalPins(grantIds: number[], userId: number): Promise<void> {
    // 保持默认的表单 Content-Type。带 cookie 时，application/json 的跨域预检会被 Access-Control-Allow-Headers: * 拦住。
    await $axios.put('/api/medal/pins', JSON.stringify({ grant_ids: grantIds }));
    refreshPlayerMedals(userId);
}

const MEDAL_STATE_ID_LIMIT = 100;
const MEDAL_STATE_CACHE_LIMIT = 200;
type MedalStateStatus = 'pending' | 'inFlight';
interface MedalStateRequest {
    promise: Promise<MedalStateRecord[]>;
    resolve: (value: MedalStateRecord[]) => void;
    reject: (reason?: unknown) => void;
    status: MedalStateStatus;
}

const medalStateCache = new Map<number, MedalStateRecord[]>();
export const medalStateVersions = shallowReactive<Record<number, number>>({});
const medalStateRequests = new Map<number, MedalStateRequest>();
let medalStateTimer: ReturnType<typeof setTimeout> | null = null;

function invalidatePlayerMedalState(userId: number) {
    medalStateCache.delete(userId);
    medalStateRequests.delete(userId);
    medalStateVersions[userId] = (medalStateVersions[userId] ?? 0) + 1;
}

function rememberMedalState(userId: number, grants: MedalStateRecord[]) {
    if (medalStateCache.has(userId)) medalStateCache.delete(userId);
    medalStateCache.set(userId, grants);
    while (medalStateCache.size > MEDAL_STATE_CACHE_LIMIT) {
        const oldest = medalStateCache.keys().next().value;
        if (oldest === undefined) break;
        medalStateCache.delete(oldest);
    }
}

function medalStateBatchSize() {
    const configured = Math.trunc(serviceConfig.value.userInfoBatchSize);
    const size = Number.isFinite(configured) ? configured : MEDAL_STATE_ID_LIMIT;
    return Math.min(MEDAL_STATE_ID_LIMIT, Math.max(1, size));
}

function scheduleMedalStateBatch() {
    if (medalStateTimer) return;
    // 同一轮里的多次读取合并成一次请求，不再等用户资料的批量延迟。
    medalStateTimer = setTimeout(() => {
        medalStateTimer = null;
        void processMedalStateBatch();
    }, 0);
}

function grantedStateRecords(grants: MedalStateRecord[] | undefined) {
    return (grants ?? []).filter((grant) => grant.stage > 0);
}

async function processMedalStateBatch() {
    const pending = [...medalStateRequests.entries()].filter(([, request]) => request.status === 'pending');
    const entries = pending.slice(0, medalStateBatchSize());
    if (entries.length === 0) return;
    entries.forEach(([, request]) => {
        request.status = 'inFlight';
    });
    const userIds = entries.map(([id]) => id);
    try {
        const { data } = await $axios.get<PlayerMedalState[]>('/api/medal/players/state', { params: { ids: userIds.join(',') } });
        const byId = new Map((data ?? []).map((row) => [row.user_id, grantedStateRecords(row.grants)]));
        for (const [userId, request] of entries) {
            const grants = byId.get(userId) ?? [];
            if (medalStateRequests.get(userId) === request) rememberMedalState(userId, grants);
            request.resolve(grants);
        }
    } catch (error) {
        entries.forEach(([, { reject }]) => {
            reject(error);
        });
    } finally {
        entries.forEach(([userId, request]) => {
            if (medalStateRequests.get(userId) === request) medalStateRequests.delete(userId);
        });
        if ([...medalStateRequests.values()].some((request) => request.status === 'pending')) scheduleMedalStateBatch();
    }
}

export function cachedPlayerMedalState(userId: number): MedalStateRecord[] | undefined {
    return medalStateCache.get(userId);
}

// 提示即将显示时读取状态，同一轮调用合并成一次请求，结果留在内存。不读玩家主页的详情接口。
export function fetchPlayerMedalState(userId: number): Promise<MedalStateRecord[]> {
    if (userId === 0) return Promise.resolve([]);
    const cached = medalStateCache.get(userId);
    if (cached) return Promise.resolve(cached);
    const existing = medalStateRequests.get(userId);
    if (existing) return existing.promise;
    const { promise, resolve, reject } = Promise.withResolvers<MedalStateRecord[]>();
    medalStateRequests.set(userId, { promise, resolve, reject, status: 'pending' });
    scheduleMedalStateBatch();
    return promise;
}

export function medalSeriesLabel(series: string, locale: string): string {
    const labels = locale.startsWith('zh') ? zhCn.medal.series : en.medal.series;
    return Object.hasOwn(labels, series) ? labels[series as MedalSeries] : series;
}

const timeSeries = new Set<string>([MedalSeries.BREAKTHROUGH, MedalSeries.FLAGLESS_BREAKTHROUGH]);
const speedSeries = new Set<string>([MedalSeries.SPEED, MedalSeries.FLAGLESS_SPEED]);
const masterySeries = new Set<string>([MedalSeries.MASTERY, MedalSeries.FLAGLESS_MASTERY]);
const precisionSeries = new Set<string>([MedalSeries.FLAGLESS_PRECISION, MedalSeries.FLAGGED_PRECISION, MedalSeries.THREE_FLAGLESS_PRECISION, MedalSeries.THREE_FLAGGED_PRECISION]);
const noviceSeries = new Set<string>([MedalSeries.REGISTERED, MedalSeries.REVIEWED, MedalSeries.LEVELS, MedalSeries.LEVELS_NF, MedalSeries.MODES, MedalSeries.SAOLEI]);
const badgeSeries = new Set<string>([MedalSeries.FLAGLESS_BREAKTHROUGH, MedalSeries.FLAGLESS_SPEED, MedalSeries.FLAGLESS_MASTERY, MedalSeries.FLAGLESS_PRECISION, MedalSeries.THREE_FLAGLESS_PRECISION]);

function trimScaled(stage: number, scale: number) {
    return (stage / scale).toFixed(5).replace(/0+$/, '').replace(/\.$/, '');
}

export function medalStageLabel(series: string, stage: number | null): string {
    if (stage == null || noviceSeries.has(series)) return '';
    if (timeSeries.has(series)) return `${zhCn.medal.sub}${stage / 1000}`;
    if (speedSeries.has(series)) return trimScaled(stage, 10000);
    if (precisionSeries.has(series)) return trimScaled(stage, 100000);
    return String(stage);
}

export function medalLevel(code: string): 'b' | 'i' | 'e' | '' {
    const matched = (/\.([bie])$/).exec(code);
    if (matched?.[1] === 'b' || matched?.[1] === 'i' || matched?.[1] === 'e') return matched[1];
    return '';
}

function fillMedalText(template: string, values: Record<string, string>) {
    return template.replace(/\{(\w+)\}/g, (_, key: string) => values[key] ?? '');
}

function medalPlainStage(series: string, stage: number | null) {
    if (stage == null) return '';
    if (series === MedalSeries.BREAKTHROUGH || series === MedalSeries.FLAGLESS_BREAKTHROUGH) return String(stage / 1000);
    return medalStageLabel(series, stage) || String(stage);
}

export function medalCaption(series: string, code: string, stage: number | null, locale: string): { title: string; meaning: string; flavor: string } {
    const chinese = locale.startsWith('zh');
    const copy = chinese ? zhCn.medal : en.medal;
    const seriesName = medalSeriesLabel(series, locale);
    const stageName = medalStageLabel(series, stage);
    const levelCode = medalLevel(code);
    const levelNames = chinese ? zhCn.level : en.level;
    const level = levelCode ? levelNames[levelCode] : '';
    let title = seriesName;
    if (stageName) {
        if ((series === MedalSeries.THREE_FLAGLESS_PRECISION || series === MedalSeries.THREE_FLAGGED_PRECISION) || !level) title = chinese ? `${seriesName}·${stageName}` : `${seriesName} · ${stageName}`;
        else if (!chinese) title = `${level} ${seriesName} · ${stageName}`;
        else title = `${level}${seriesName}·${stageName}`;
    }
    const values = { level, value: medalPlainStage(series, stage) };
    return {
        title,
        meaning: Object.hasOwn(copy.meaning, series) ? fillMedalText(copy.meaning[series as MedalSeries], values) : '',
        flavor: Object.hasOwn(copy.flavor, series) ? copy.flavor[series as keyof typeof copy.flavor] : '',
    };
}

const medalCodeSeries = [
    ['ability.time.nf.', MedalSeries.FLAGLESS_BREAKTHROUGH],
    ['ability.time.', MedalSeries.BREAKTHROUGH],
    ['ability.bvs.nf.', MedalSeries.FLAGLESS_SPEED],
    ['ability.bvs.', MedalSeries.SPEED],
    ['ability.stnb.nf.', MedalSeries.FLAGLESS_MASTERY],
    ['ability.stnb.', MedalSeries.MASTERY],
    ['ability.thrp.nf.three', MedalSeries.THREE_FLAGLESS_PRECISION],
    ['ability.thrp.nf.', MedalSeries.FLAGLESS_PRECISION],
    ['ability.thrp.fl.three', MedalSeries.THREE_FLAGGED_PRECISION],
    ['ability.thrp.fl.', MedalSeries.FLAGGED_PRECISION],
    ['novice.realname', MedalSeries.REGISTERED],
    ['novice.review', MedalSeries.REVIEWED],
    ['novice.levels_nf', MedalSeries.LEVELS_NF],
    ['novice.levels', MedalSeries.LEVELS],
    ['novice.modes', MedalSeries.MODES],
    ['novice.saolei', MedalSeries.SAOLEI],
    ['shareholder.', MedalSeries.SHAREHOLDER],
] as const;

const medalSeriesByCodePrefix = [...medalCodeSeries].sort((left, right) => right[0].length - left[0].length);

export function medalSeriesFromCode(code: string): string {
    const matched = medalSeriesByCodePrefix.find(([prefix]) => code.startsWith(prefix));
    return matched?.[1] ?? '';
}

const medalArtFolder: Record<string, string> = {
    [MedalSeries.BREAKTHROUGH]: 'breakthrough',
    [MedalSeries.SPEED]: 'speed',
    [MedalSeries.MASTERY]: 'mastery',
    [MedalSeries.FLAGLESS_BREAKTHROUGH]: 'breakthrough-nf',
    [MedalSeries.FLAGLESS_SPEED]: 'speed-nf',
    [MedalSeries.FLAGLESS_MASTERY]: 'mastery-nf',
    [MedalSeries.FLAGLESS_PRECISION]: 'precision-nf',
    [MedalSeries.FLAGGED_PRECISION]: 'precision',
    [MedalSeries.THREE_FLAGLESS_PRECISION]: 'precision-nf-three',
    [MedalSeries.THREE_FLAGGED_PRECISION]: 'precision-three',
    [MedalSeries.REGISTERED]: 'registered',
    [MedalSeries.REVIEWED]: 'reviewed',
    [MedalSeries.LEVELS]: 'levels',
    [MedalSeries.LEVELS_NF]: 'levels-nf',
    [MedalSeries.MODES]: 'modes',
    [MedalSeries.SAOLEI]: 'saolei',
    [MedalSeries.SHAREHOLDER]: 'shareholder',
};

export function medalArtMetal(series: string, code: string, stage: number | null): 'b' | 'i' | 'e' {
    const level = medalLevel(code);
    if (level) return level;
    if (series !== MedalSeries.SHAREHOLDER) return 'e';
    // 越晚偏铜，居中偏银，最早保持金色。
    if (stage != null && stage <= 1000) return 'e';
    if (stage != null && stage <= 10000) return 'i';
    return 'b';
}

export function medalArtBadge(series: string): boolean {
    return badgeSeries.has(series);
}

/** 叠在底图上的短数字。称号里的 Sub 前缀和系列名仍由页面文案显示。 */
export function medalArtPlate(series: string, stage: number | null): string {
    if (stage == null || noviceSeries.has(series) || series === MedalSeries.SHAREHOLDER) return '';
    if (timeSeries.has(series)) return String(stage / 1000);
    if (speedSeries.has(series)) return trimScaled(stage, 10000);
    if (precisionSeries.has(series)) return trimScaled(stage, 100000);
    if (masterySeries.has(series)) return String(stage);
    return '';
}

export function medalArtUrl(series: string, code: string, stage: number | null): string | undefined {
    const folder = medalArtFolder[series];
    if (!folder || stage == null || !code) return undefined;
    // 铜和银由前端从这张金色底图换色。v=5 让浏览器丢掉按金属色缓存的旧图。
    return `${import.meta.env.BASE_URL}assets/medals/${folder}.webp?v=5`;
}
