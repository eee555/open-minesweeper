import type { CursorPosition } from './replayCursor';

export interface BoardFrame {
    board: number[][] | null;
    globalBoard: number[][] | null;
    probabilityBoard: number[][] | null;
    cursorPosition: CursorPosition | null;
    mouseState: number;
    currentEventIndex: number | null;
    nativeCellSize: number | null;
}
