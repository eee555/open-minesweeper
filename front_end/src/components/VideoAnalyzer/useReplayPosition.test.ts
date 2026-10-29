import { readFileSync } from 'node:fs';

import { GameBoard, VideoActionStateRecorder } from 'ms-toollib';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { effectScope, nextTick, ref, shallowRef } from 'vue';
import type { EffectScope } from 'vue';

import { readCounterEvents } from './counter';
import { parseReplay } from './replayParser';
import type { ReplayVideo } from './replayParser';
import { useReplayPosition } from './useReplayPosition';

const scopes: EffectScope[] = [];
const videos: ReplayVideo[] = [];

function loadFixture(filename = '52200.evf', software: Parameters<typeof parseReplay>[2] = 'e') {
    const bytes = Uint8Array.from(readFileSync(new URL(`../../../cypress/fixtures/${filename}`, import.meta.url)));
    const video = parseReplay(bytes.buffer, filename, software);
    videos.push(video);
    return video;
}

function setup(initialVideo: ReplayVideo | null = null) {
    const video = shallowRef(initialVideo);
    const currentMs = ref(0);
    const scope = effectScope();
    scopes.push(scope);
    const position = scope.run(() => useReplayPosition(video, currentMs));
    if (position === undefined) throw new Error('Position scope did not start');
    return { video, currentMs, ...position, scope };
}

function openedCells(board: number[][] | null) {
    return board?.flat().filter((cell) => cell >= 0 && cell <= 8).length;
}

function priorSnapshot(video: ReplayVideo, index: number) {
    const records = video.events as VideoActionStateRecorder[];
    try {
        const board = records[index].prior_game_board;
        try {
            return { board: board.game_board as number[][], probability: board.poss as number[][] };
        } finally {
            board.free();
        }
    } finally {
        for (const record of records) record.free();
    }
}

afterEach(() => {
    for (const scope of scopes.splice(0)) scope.stop();
    for (const video of videos.splice(0)) video.free();
    vi.restoreAllMocks();
});

describe('analyzer replay position', () => {
    it('waits for a loaded replay and positions it at the shared time', async () => {
        const state = setup();
        expect(state.gameBoard.value).toBeNull();
        expect(state.probabilityBoard.value).toBeNull();
        expect(state.currentEventIndex.value).toBeNull();
        expect(state.cursorPosition.value).toBeNull();
        state.currentMs.value = 5000;
        state.video.value = loadFixture();
        await nextTick();
        expect(openedCells(state.gameBoard.value)).toBe(180);
        expect(state.gameBoard.value).toEqual(state.video.value.game_board);
        expect(state.probabilityBoard.value).toEqual(state.video.value.game_board_poss);
    });

    it('does not initially display the analysed terminal board', () => {
        const video = loadFixture();
        const state = setup(video);
        expect(video.bbbv_solved).toBe(1);
        expect(openedCells(state.gameBoard.value)).toBe(128);
        expect(state.gameBoard.value?.[0][1]).toBe(10);
    });

    it('seeks forwards and backwards without mutating older snapshots', async () => {
        const state = setup(loadFixture());
        const initial = state.gameBoard.value;
        state.currentMs.value = 5000;
        await nextTick();
        expect(openedCells(state.gameBoard.value)).toBe(180);
        expect(openedCells(initial)).toBe(128);
        state.currentMs.value = 0;
        await nextTick();
        expect(state.gameBoard.value).toEqual(initial);
    });

    it('includes the final event at duration and restores the start after loop wrap', async () => {
        const video = loadFixture();
        const state = setup(video);
        state.currentMs.value = video.rtime_ms;
        await nextTick();
        expect(video.bbbv_solved).toBe(52);
        expect(video.cl).toBe(63);
        expect(openedCells(state.gameBoard.value)).toBe(216);
        state.currentMs.value = 0;
        await nextTick();
        expect(video.bbbv_solved).toBe(1);
        expect(openedCells(state.gameBoard.value)).toBe(128);
    });

    it('keeps special cell states exactly as returned by game_board', async () => {
        const video = loadFixture();
        const board = video.game_board as number[][];
        board[0][0] = 15;
        vi.spyOn(video, 'game_board', 'get').mockReturnValue(board);
        const state = setup(video);
        state.currentMs.value = video.rtime_ms;
        await nextTick();
        expect(state.gameBoard.value).toEqual(board);
        expect(state.gameBoard.value?.flat()).toContain(15);
    });

    it('clears the board when unloaded and positions a replacement at unchanged time', async () => {
        const state = setup(loadFixture());
        state.currentMs.value = 5000;
        await nextTick();
        state.video.value = null;
        await nextTick();
        expect(state.gameBoard.value).toBeNull();
        expect(state.probabilityBoard.value).toBeNull();
        expect(state.currentEventIndex.value).toBeNull();
        state.video.value = loadFixture();
        await nextTick();
        expect(openedCells(state.gameBoard.value)).toBe(180);
        expect(state.probabilityBoard.value).toEqual(state.video.value.game_board_poss);
    });

    it('stops accessing the parser after its page scope is disposed', async () => {
        const video = loadFixture();
        const position = vi.spyOn(Object.getPrototypeOf(video) as ReplayVideo, 'current_time', 'set');
        const state = setup(video);
        expect(position).toHaveBeenCalledOnce();
        state.scope.stop();
        state.currentMs.value = 5000;
        await nextTick();
        expect(position).toHaveBeenCalledOnce();
    });

    for (const [filename, software] of [
        ['52200.evf', 'e'],
        ['Exp_FL_35.09_3BV=132_3BVs=3.76_Pu Tian Yi(Hu Bei).avf', 'a'],
        ['Lin_Jin_Fan_Exp_60.623bv207.mvf', 'm'],
        ['3819-Time-1616-NF-9469-32-20151031.rmv', 'r'],
    ] as const) {
        it(`sets time before event index and renders the prior board for ${filename}`, async () => {
            const video = loadFixture(filename, software);
            const events = readCounterEvents(video);
            const buttons = events.filter((event) => event.button);
            const frame = buttons[Math.floor(buttons.length / 2)];
            const expected = priorSnapshot(video, frame.eventIndex);
            const state = setup(video);
            const timeSetter = vi.spyOn(video, 'current_time', 'set');
            const indexSetter = vi.spyOn(video, 'current_event_id', 'set');
            const recordFree = vi.spyOn(VideoActionStateRecorder.prototype, 'free');
            const boardFree = vi.spyOn(GameBoard.prototype, 'free');
            state.currentMs.value = frame.timeMs;
            state.selectKeyframe(frame.eventIndex);
            await nextTick();
            expect(timeSetter).toHaveBeenCalledOnce();
            expect(timeSetter).toHaveBeenCalledWith(frame.timeMs / 1000);
            expect(indexSetter).toHaveBeenCalledOnce();
            expect(indexSetter).toHaveBeenCalledWith(frame.eventIndex);
            expect(timeSetter.mock.invocationCallOrder[0]).toBeLessThan(indexSetter.mock.invocationCallOrder[0]);
            expect(state.currentEventIndex.value).toBe(frame.eventIndex);
            expect(state.gameBoard.value).toEqual(expected.board);
            expect(state.probabilityBoard.value).toEqual(expected.probability);
            expect(recordFree).toHaveBeenCalledTimes(events.length);
            expect(boardFree).toHaveBeenCalledOnce();
        });
    }

    it('distinguishes equal-timestamp frames and restores normal positioning even when seeking to the same time', async () => {
        const video = loadFixture('Exp_FL_35.09_3BV=132_3BVs=3.76_Pu Tian Yi(Hu Bei).avf', 'a');
        const buttons = readCounterEvents(video).filter((event) => event.button && event.timeMs === 2910);
        const state = setup(video);
        state.currentMs.value = 2910;
        await nextTick();
        const normal = state.gameBoard.value;
        expect(buttons).toHaveLength(2);
        for (const frame of [...buttons].reverse()) {
            const prior = priorSnapshot(video, frame.eventIndex);
            state.selectKeyframe(frame.eventIndex);
            await nextTick();
            expect(state.currentMs.value).toBe(2910);
            expect(state.currentEventIndex.value).toBe(frame.eventIndex);
            expect(state.gameBoard.value).toEqual(prior.board);
        }
        expect(state.gameBoard.value).not.toEqual(normal);
        state.clearKeyframe();
        await nextTick();
        expect(state.gameBoard.value).toEqual(normal);
        expect(state.probabilityBoard.value).toEqual(video.game_board_poss);
    });

    it('clears the event override on playback advance and replay replacement', async () => {
        const state = setup(loadFixture());
        state.selectKeyframe(0);
        await nextTick();
        expect(openedCells(state.gameBoard.value)).toBe(0);
        state.currentMs.value = 1;
        await nextTick();
        expect(state.gameBoard.value).toEqual(state.video.value?.game_board);
        expect(openedCells(state.gameBoard.value)).toBe(128);
        state.selectKeyframe(0);
        await nextTick();
        state.video.value = null;
        await nextTick();
        expect(state.currentEventIndex.value).toBeNull();
        expect(state.gameBoard.value).toBeNull();
        state.video.value = loadFixture();
        await nextTick();
        expect(state.gameBoard.value).toEqual(state.video.value.game_board);
    });

    it('reads and releases cursor snapshots at the same position, including rewind and loop wrap', async () => {
        const video = loadFixture();
        const state = setup(video);
        const start = state.cursorPosition.value;
        expect(start).toEqual({ columnIndex: 166 / 26, rowIndex: 35 / 26 });
        const position = vi.spyOn(Object.getPrototypeOf(video) as ReplayVideo, 'current_time', 'set');
        let reads = 0;
        for (const ms of [1000, 5000, video.rtime_ms, 0]) {
            state.currentMs.value = ms;
            await nextTick();
            const cursor = video.x_y;
            try {
                expect(state.cursorPosition.value).toEqual({ columnIndex: cursor.x / video.pix_size, rowIndex: cursor.y / video.pix_size });
            } finally {
                cursor.free();
            }
            expect(position).toHaveBeenCalledTimes(++reads);
        }
        expect(state.cursorPosition.value).toEqual(start);
        expect(start).toEqual({ columnIndex: 166 / 26, rowIndex: 35 / 26 });
        state.video.value = null;
        await nextTick();
        expect(state.cursorPosition.value).toBeNull();
    });

    it('hides invalid cursor positions, accepts the origin and always frees the wrapper', () => {
        const video = loadFixture();
        for (const [x, y] of [[NaN, 0], [0, Infinity], [-1, 0], [65535, 65535], [0, 0]]) {
            const cursor = { x, y, free: vi.fn() };
            const getter = vi.spyOn(Object.getPrototypeOf(video) as ReplayVideo, 'x_y', 'get').mockReturnValue(cursor as unknown as ReplayVideo['x_y']);
            const state = setup(video);
            expect(state.cursorPosition.value).toEqual(x === 0 && y === 0 ? { columnIndex: 0, rowIndex: 0 } : null);
            expect(cursor.free).toHaveBeenCalledOnce();
            state.scope.stop();
            getter.mockRestore();
        }
    });

    for (const filename of ['52200.evf', 'c_10_39.832_24_0.477_Pu Tian Yi(Hu Bei)_fail.evf']) {
        it(`reads probability and opened snapshots at the same time for ${filename}`, async () => {
            const video = loadFixture(filename);
            const position = vi.spyOn(Object.getPrototypeOf(video) as ReplayVideo, 'current_time', 'set');
            const state = setup(video);
            const initial = state.probabilityBoard.value;
            const initialCopy = initial?.map((row) => [...row]);
            let positions = 1;
            for (const ms of [5000, video.rtime_ms, 0]) {
                state.currentMs.value = ms;
                await nextTick();
                expect(position).toHaveBeenCalledTimes(++positions);
                expect(state.gameBoard.value).toEqual(video.game_board);
                expect(state.probabilityBoard.value).toEqual(video.game_board_poss);
                if (filename === '52200.evf' && ms === 5000) expect(state.probabilityBoard.value).not.toEqual(initial);
                expect(state.probabilityBoard.value).toHaveLength(video.row);
                for (const row of state.probabilityBoard.value ?? []) {
                    expect(row).toHaveLength(video.column);
                    expect(row.every((value) => value >= 0 && value <= 1)).toBe(true);
                }
            }
            expect(initial).toEqual(initialCopy);
            expect(state.probabilityBoard.value).toEqual(initial);
        });
    }
});
