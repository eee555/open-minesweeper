/** Viewer preferences only. Tier assignment comes from the reviewed medal definition. */
export const MEDAL_PALETTE_KEY = 'medal-appearance-colors-v1';
export const DEFAULT_MEDAL_COLORS = ['#244A86', '#4C91C7', '#CCB8E3', '#F2CE9B', '#B34A55'] as const;
export const MAX_MEDAL_PALETTE_JSON_LENGTH = 65536;

export interface MedalPaletteConfig {
    version: 1;
    colors: string[];
    stages: Record<string, Record<string, string>>;
}

export interface PaletteStorage {
    getItem: (key: string) => string | null;
    setItem: (key: string, value: string) => void;
}

export function defaultMedalPalette(): MedalPaletteConfig {
    return { version: 1, colors: [...DEFAULT_MEDAL_COLORS], stages: {} };
}

export function normalizeMedalColor(value: unknown): string {
    if (typeof value !== 'string' || !(/^#[\da-f]{6}$/i).test(value.trim())) throw new Error('颜色须为 #RRGGBB 格式。');
    return value.trim().toUpperCase();
}

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function parseMedalPalette(raw: string): MedalPaletteConfig {
    if (raw.length > MAX_MEDAL_PALETTE_JSON_LENGTH) throw new Error('配色文件不能超过 64 KiB 字符。');
    const data: unknown = JSON.parse(raw);
    if (!isRecord(data) || data.version !== 1 || !Array.isArray(data.colors) || data.colors.length !== 5 || !isRecord(data.stages)) {
        throw new Error('需要 version: 1、五种 colors 和 stages 对象。');
    }
    const colors = data.colors.map(normalizeMedalColor);
    const stages: Record<string, Record<string, string>> = {};
    const codes = Object.entries(data.stages);
    if (codes.length > 128) throw new Error('门槛配色类别过多。');
    for (const [code, values] of codes) {
        if (!(/^[a-z][a-z0-9]*(?:\.[a-z0-9]+)+$/).test(code) || !isRecord(values)) throw new Error('门槛配色的称号代码无效。');
        const entries = Object.entries(values);
        if (entries.length > 128) throw new Error('单个称号的门槛配色过多。');
        const overrides: Record<string, string> = {};
        for (const [stage, color] of entries) {
            if (!(/^[1-9]\d*$/).test(stage) || !Number.isSafeInteger(Number(stage))) throw new Error('门槛必须是正整数，不是档位序号。');
            overrides[stage] = normalizeMedalColor(color);
        }
        stages[code] = overrides;
    }
    return { version: 1, colors, stages };
}

/** Exact threshold override, then a reviewed 1–5 tier; unknown mappings stay unknown. */
export function medalPaletteColor(config: MedalPaletteConfig, tier: number | undefined, code: string, stage: number | null): string | undefined {
    if (stage !== null && Object.hasOwn(config.stages, code)) {
        const overrides = config.stages[code];
        if (Object.hasOwn(overrides, String(stage))) return overrides[String(stage)];
    }
    return tier !== undefined && Number.isInteger(tier) && tier >= 1 && tier <= 5 ? config.colors[tier - 1] : undefined;
}

export function loadMedalPalette(storage: PaletteStorage | undefined): { config: MedalPaletteConfig; status: 'saved' | 'default' | 'invalid' | 'unavailable' } {
    let raw: string | null;
    try {
        if (!storage) return { config: defaultMedalPalette(), status: 'unavailable' };
        raw = storage.getItem(MEDAL_PALETTE_KEY);
    } catch {
        return { config: defaultMedalPalette(), status: 'unavailable' };
    }
    if (raw === null) return { config: defaultMedalPalette(), status: 'default' };
    try {
        return { config: parseMedalPalette(raw), status: 'saved' };
    } catch {
        return { config: defaultMedalPalette(), status: 'invalid' };
    }
}

export function saveMedalPalette(storage: PaletteStorage | undefined, config: MedalPaletteConfig): boolean {
    if (!storage) return false;
    try {
        const validated = parseMedalPalette(JSON.stringify(config));
        storage.setItem(MEDAL_PALETTE_KEY, JSON.stringify(validated));
        return true;
    } catch {
        return false;
    }
}
