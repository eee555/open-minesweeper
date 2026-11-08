import { getDatabase, VIDEO_INFO_STORE_NAME } from '../../src/services/database';
import type { VideoMetadata } from '../../src/services/videoInfoService';

function parsedVideoRows(rows: Record<string, unknown>[]) {
    return rows.map((row) => ({
        id: Number(row.id),
        ongoing_tournament: row.ongoing_tournament ?? false,
        software: row.software ?? 'e',
        level: row.level ?? 'b',
        mode: row.mode ?? '00',
        end_time: row.end_time ?? null,
        file_size: row.file_size ?? 123,
        timems: row.timems ?? 1000,
        bv: row.bv ?? 4,
        left: row.left ?? row.cl ?? null,
        right: row.right ?? 0,
        double: row.double ?? 0,
        left_ce: row.left_ce ?? (typeof row.ce === 'number' ? row.ce - Number(row.right_ce ?? 1) : null),
        right_ce: row.right_ce ?? (row.ce === undefined ? null : 1),
        double_ce: row.double_ce ?? 0,
        path: row.path ?? null,
        pluck: row.pluck ?? null,
        flag: row.flag ?? 0,
        op: row.op ?? 1,
        isl: row.isl ?? 0,
        cell0: 0,
        cell1: 0,
        cell2: 0,
        cell3: 0,
        cell4: 0,
        cell5: 0,
        cell6: 0,
        cell7: 0,
        cell8: 0,
        identifier: row.identifier ?? '',
        tournament_identifier: row.tournament_identifier ?? [],
    }));
}

/** Split existing replay fixtures into the same metadata/parsed-field responses as production. */
export function mockVideoInfo(rows: Record<string, unknown>[], metadataAlias = 'videoMetadata'): (VideoMetadata & { player__id?: number; player__realname?: string })[] {
    cy.then(async () => {
        await (await getDatabase()).clear(VIDEO_INFO_STORE_NAME);
    });
    const videos = rows.map((row) => ({
        id: Number(row.id),
        ongoing_tournament: Boolean(row.ongoing_tournament),
        player: Number(row.player ?? row.player_id ?? 7),
        upload_time: typeof row.upload_time === 'string' ? row.upload_time : typeof row.time === 'string' ? row.time : '2026-10-22T00:00:00Z',
        state: typeof row.state === 'string' ? row.state : 'c',
        ...row.player__id === undefined ? {} : { player__id: Number(row.player__id), player__realname: typeof row.player__realname === 'string' ? row.player__realname : '' },
    }));
    const parsed = parsedVideoRows(rows);
    cy.intercept('GET', '**/api/video/abstractbulk*', (request) => {
        const first = Math.max(1, Number(request.query.first));
        const count = Math.max(1, Math.min(10000, Number(request.query.count)));
        request.reply({ body: videos.filter((row) => !row.ongoing_tournament && row.id >= first && row.id < first + count).map((row) => ({ id: row.id, player: row.player, upload_time: row.upload_time, state: row.state })) });
    }).as(metadataAlias);
    cy.intercept('GET', '**/api/video/staticdetailbatch*', (request) => {
        const ids = String(request.query.ids).split(',').map(Number);
        request.reply({ body: parsed.filter((row) => ids.includes(row.id)) });
    }).as('parsedVideoInfo');
    return videos;
}

/** Preload public parsed rows so components resolve them without the shared, debounced batch queue. */
export function seedVideoInfoCache(rows: Record<string, unknown>[]): void {
    cy.then(async () => {
        const db = await getDatabase();
        for (const row of parsedVideoRows(rows)) {
            if (row.ongoing_tournament !== false) continue;
            const data = { ...row };
            Reflect.deleteProperty(data, 'ongoing_tournament');
            await db.put(VIDEO_INFO_STORE_NAME, { id: row.id, scope: 'public', data });
        }
    });
}
