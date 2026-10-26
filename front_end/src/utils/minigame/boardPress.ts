export interface BoardPress {
    readonly row: number;
    readonly column: number;
    readonly chord: boolean;
}

// 主棋盘编码的自然压下状态；只覆盖背景，数字、雷和旗的前景由原组件绘制。
const downValues = new Set([0, 1, 2, 3, 4, 5, 6, 7, 8, 14, 15, 18]);

export function pressedBackground(board: readonly (readonly number[])[], press: BoardPress | null, minePressed = false): boolean[][] | undefined {
    if (press === null && !minePressed) return undefined;
    return board.map((row, r) => row.map((value, c) => {
        if (value === 11) return false;
        const inside = press !== null && (press.chord ? Math.abs(r - press.row) <= 1 && Math.abs(c - press.column) <= 1 : r === press.row && c === press.column);
        return inside || downValues.has(value) || (minePressed && value === 16);
    }));
}
