import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { MedalOverrideInput, StaffMedalDefinition } from './staffMedalService';
import { fetchStaffMedalCatalog, fetchStaffPlayerMedals, setMedalOverride, staffMedalStages, validMedalOverride } from './staffMedalService';

import { MedalDirection, MedalKind, MedalSeries } from '@/utils/medal_const';

const { get, post, refreshPlayerMedals } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), refreshPlayerMedals: vi.fn() }));
vi.mock('@/http', () => ({ default: { get, post } }));
vi.mock('./medalService', () => ({ refreshPlayerMedals }));

const definition: StaffMedalDefinition = {
    code: 'time.b',
    series: MedalSeries.BREAKTHROUGH,
    subseries: '',
    kind: MedalKind.PB,
    metric: 'time',
    direction: MedalDirection.DESC,
    level: 'b',
    style: '',
    thresholds: [10_000, 20_000],
    active: true,
    hidden: false,
};
const input: MedalOverrideInput = {
    user_id: 42, code: 'time.b', scope_key: '', mode: 'grant', reason: 'Manual award', stage: 10_000, granted_on: '2026-10-23',
};

describe('staff medal management', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('requires an active definition, a legal stage, date and reason for forced grants', () => {
        expect(validMedalOverride(input, definition, false)).toBe(true);
        expect(validMedalOverride({ ...input, stage: 15_000 }, definition, false)).toBe(false);
        expect(validMedalOverride({ ...input, stage: undefined }, definition, false)).toBe(false);
        expect(validMedalOverride({ ...input, reason: '   ' }, definition, false)).toBe(false);
        expect(validMedalOverride({ ...input, granted_on: '2026-02-30' }, definition, false)).toBe(false);
        expect(validMedalOverride({ ...input, granted_on: undefined }, definition, false)).toBe(false);
        expect(validMedalOverride(input, { ...definition, active: false }, false)).toBe(false);
        expect(validMedalOverride(input, undefined, false)).toBe(false);
    });

    it('permits blocking a medal before a grant exists without stage or date', () => {
        expect(validMedalOverride({ ...input, mode: 'revoke', stage: undefined, granted_on: undefined }, definition, false)).toBe(true);
    });

    it('offers the default stage 1 for manual medals without configured thresholds', () => {
        const manual = { ...definition, kind: MedalKind.MANUAL, thresholds: [] };
        expect(staffMedalStages(manual)).toEqual([1]);
        expect(validMedalOverride({ ...input, stage: 1 }, manual, false)).toBe(true);
        expect(validMedalOverride({ ...input, stage: 2 }, manual, false)).toBe(false);
        expect(validMedalOverride({ ...input, stage: 1 }, { ...definition, thresholds: [] }, false)).toBe(false);
    });

    it('rejects scoped ordinary grants and blocks, while allowing legacy overrides to be removed', () => {
        for (const kind of [MedalKind.PB, MedalKind.ONCE, MedalKind.COMPOSITE, MedalKind.COUNT, MedalKind.BV_SET, MedalKind.CELL_MASK, MedalKind.MIN_VIDEO_ID]) {
            expect(validMedalOverride({ ...input, scope_key: '2026' }, { ...definition, kind }, false)).toBe(false);
            expect(validMedalOverride({ ...input, scope_key: '2026', mode: 'revoke' }, { ...definition, kind }, false)).toBe(false);
            expect(validMedalOverride({ ...input, scope_key: '2026', mode: 'auto' }, { ...definition, kind }, true)).toBe(true);
        }
        for (const kind of [MedalKind.MANUAL, MedalKind.EVENT_PLACE, MedalKind.GSC_STAT, MedalKind.GSC_PLACE]) {
            expect(validMedalOverride({ ...input, scope_key: '2026' }, { ...definition, kind }, false)).toBe(true);
        }
    });

    it('requires an override to restore automatic awards, including removed definitions', () => {
        const automatic: MedalOverrideInput = { user_id: 42, code: 'deleted', scope_key: '2026', mode: 'auto', reason: 'Release lock' };
        expect(validMedalOverride(automatic, undefined, true)).toBe(true);
        expect(validMedalOverride(automatic, { ...definition, active: false }, true)).toBe(true);
        expect(validMedalOverride(automatic, definition, false)).toBe(false);
        expect(validMedalOverride({ ...automatic, user_id: 0 }, definition, true)).toBe(false);
    });

    it('loads the staff catalog and player detail from their separate endpoints', async () => {
        get.mockResolvedValueOnce({ data: [definition] });
        expect(await fetchStaffMedalCatalog()).toEqual([definition]);
        expect(get).toHaveBeenLastCalledWith('/api/medal/staff/catalog');
        const player = { user_id: 42, username: 'Player', grants: [], overrides: [], history: [] };
        get.mockResolvedValueOnce({ data: player });
        expect(await fetchStaffPlayerMedals(42)).toEqual(player);
        expect(get).toHaveBeenLastCalledWith('/api/medal/staff/players/42');
    });

    it('preserves the chosen stage, award date, reason and scope in the JSON payload', async () => {
        const result = { grant_id: 1, mode: 'grant', enqueued: false };
        post.mockResolvedValue({ data: result });
        expect(await setMedalOverride(input)).toEqual(result);
        expect(post).toHaveBeenCalledWith('/api/medal/staff/overrides', JSON.stringify(input));
        expect(refreshPlayerMedals).toHaveBeenCalledOnce();
        expect(refreshPlayerMedals).toHaveBeenCalledWith(input.user_id);
    });

    it('does not add grant-only fields to a restore-automatic request', async () => {
        const automatic: MedalOverrideInput = { user_id: 42, code: 'time.b', scope_key: '2026', mode: 'auto', reason: 'Release lock' };
        post.mockResolvedValue({ data: { grant_id: null, mode: 'auto', enqueued: true } });
        expect((await setMedalOverride(automatic)).enqueued).toBe(true);
        expect(post).toHaveBeenCalledWith('/api/medal/staff/overrides', JSON.stringify(automatic));
        expect(refreshPlayerMedals).toHaveBeenCalledWith(automatic.user_id);
    });

    it('refreshes the affected player after a successful revoke and preserves caches when saving fails', async () => {
        const revoke: MedalOverrideInput = { user_id: 3, code: 'shareholder.origin', scope_key: '', mode: 'revoke', reason: 'Test revoke' };
        post.mockResolvedValueOnce({ data: { grant_id: 49, mode: 'revoke', enqueued: false } });
        await setMedalOverride(revoke);
        expect(refreshPlayerMedals).toHaveBeenCalledOnce();
        expect(refreshPlayerMedals).toHaveBeenCalledWith(3);
        refreshPlayerMedals.mockClear();
        post.mockRejectedValueOnce(new Error('Save failed'));
        await expect(setMedalOverride(revoke)).rejects.toThrow('Save failed');
        expect(refreshPlayerMedals).not.toHaveBeenCalled();
    });
});
