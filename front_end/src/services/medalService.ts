import { serviceConfig } from './store';

import $axios from '@/http';
import en from '@/i18n/locales/en';
import zhCn from '@/i18n/locales/zh-cn';

export interface MedalItem {
    code: string;
    series: string;
    subseries: string;
    kind: string;
    stage: number | null;
    stage_count: number;
    direction: 'asc' | 'desc';
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
const medalStateRequests = new Map<number, MedalStateRequest>();
let medalStateTimer: ReturnType<typeof setTimeout> | null = null;

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
    medalStateTimer = setTimeout(() => {
        medalStateTimer = null;
        void processMedalStateBatch();
    }, serviceConfig.value.userInfoBatchDelay);
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
        for (const [userId, { resolve }] of entries) {
            const grants = byId.get(userId) ?? [];
            rememberMedalState(userId, grants);
            resolve(grants);
        }
    } catch (error) {
        entries.forEach(([, { reject }]) => {
            reject(error);
        });
    } finally {
        entries.forEach(([userId]) => {
            medalStateRequests.delete(userId);
        });
        if ([...medalStateRequests.values()].some((request) => request.status === 'pending')) scheduleMedalStateBatch();
    }
}

// 名字出现时收集 id，延迟后打一次状态接口，结果留在内存。不读玩家主页的详情接口。
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

const medalSeriesKeys: Record<string, keyof typeof en.medal.series> = {
    破境: 'breakthrough',
    神速: 'speed',
    通明: 'mastery',
    盲扫破境: 'flaglessBreakthrough',
    盲扫神速: 'flaglessSpeed',
    盲扫通明: 'flaglessMastery',
    盲扫·精工: 'flaglessPrecision',
    标旗·精工: 'flaggedPrecision',
    三阶盲扫·精工: 'threeTierFlaglessPrecision',
    三阶标旗·精工: 'threeTierFlaggedPrecision',
    实名在册: 'registered',
    录像过审: 'reviewed',
    扫雷新秀: 'firstGlimpse',
    盲扫新秀: 'anotherPath',
    走马观花: 'grandTour',
    旧迹新篇: 'oldTraces',
    原始股东: 'shareholder',
};

export function medalSeriesLabel(series: string, locale: string): string {
    const key = medalSeriesKeys[series];
    if (!key) return series;
    return (locale.startsWith('zh') ? zhCn.medal.series : en.medal.series)[key];
}

const timeSeries = new Set(['破境', '盲扫破境']);
const speedSeries = new Set(['神速', '盲扫神速']);
const masterySeries = new Set(['通明', '盲扫通明']);
const precisionSeries = new Set(['盲扫·精工', '标旗·精工', '三阶盲扫·精工', '三阶标旗·精工']);
const noviceSeries = new Set(['实名在册', '录像过审', '扫雷新秀', '盲扫新秀', '走马观花', '旧迹新篇']);
const badgeSeries = new Set(['盲扫破境', '盲扫神速', '盲扫通明', '盲扫·精工', '三阶盲扫·精工']);

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

const medalCodeSeries = [
    ['ability.time.nf.', '盲扫破境'],
    ['ability.time.', '破境'],
    ['ability.bvs.nf.', '盲扫神速'],
    ['ability.bvs.', '神速'],
    ['ability.stnb.nf.', '盲扫通明'],
    ['ability.stnb.', '通明'],
    ['ability.thrp.nf.three', '三阶盲扫·精工'],
    ['ability.thrp.nf.', '盲扫·精工'],
    ['ability.thrp.fl.three', '三阶标旗·精工'],
    ['ability.thrp.fl.', '标旗·精工'],
    ['novice.realname', '实名在册'],
    ['novice.review', '录像过审'],
    ['novice.levels_nf', '盲扫新秀'],
    ['novice.levels', '扫雷新秀'],
    ['novice.modes', '走马观花'],
    ['novice.saolei', '旧迹新篇'],
    ['shareholder.', '原始股东'],
] as const;

const medalSeriesByCodePrefix = [...medalCodeSeries].sort((left, right) => right[0].length - left[0].length);

export function medalSeriesFromCode(code: string): string {
    const matched = medalSeriesByCodePrefix.find(([prefix]) => code.startsWith(prefix));
    return matched?.[1] ?? '';
}

const medalArtFolder: Record<string, string> = {
    破境: 'breakthrough',
    神速: 'speed',
    通明: 'mastery',
    盲扫破境: 'breakthrough-nf',
    盲扫神速: 'speed-nf',
    盲扫通明: 'mastery-nf',
    盲扫·精工: 'precision-nf',
    标旗·精工: 'precision',
    三阶盲扫·精工: 'precision-nf-three',
    三阶标旗·精工: 'precision-three',
    实名在册: 'registered',
    录像过审: 'reviewed',
    扫雷新秀: 'levels',
    盲扫新秀: 'levels-nf',
    走马观花: 'modes',
    旧迹新篇: 'saolei',
    原始股东: 'shareholder',
};

export function medalArtMetal(series: string, code: string, stage: number | null): 'b' | 'i' | 'e' {
    const level = medalLevel(code);
    if (level) return level;
    if (series !== '原始股东') return 'e';
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
    if (stage == null || noviceSeries.has(series) || series === '原始股东') return '';
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
