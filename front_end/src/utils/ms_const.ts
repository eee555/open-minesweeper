import { useLocalStorage } from '@vueuse/core';

export const MS_Levels = ['b', 'i', 'e'] as const;
export type MS_Level = typeof MS_Levels[number];

export function isStandardLevel(level: unknown): level is MS_Level {
    return typeof level === 'string' && (MS_Levels as readonly string[]).includes(level);
}

export const MS_Softwares = ['e', 'a', 'r', 'm', 'x'] as const;
export type MS_Software = typeof MS_Softwares[number];

export const STNB_const = useLocalStorage('stnb_const', {
    b: 36,
    i: 162,
    e: 435,
});

export const MS_Mode = {
    Standard: '00',
    SpeedNG: '05',
    HardcoreNG: '06',
    Lucky: '10',
    Recursive: '11',
} as const;
export type MS_Mode = typeof MS_Mode[keyof typeof MS_Mode];

export const MS_State = {
    Plain: 'a',
    Frozen: 'b',
    Official: 'c',
    Identifier: 'd',
    Local: 'l',
} as const;
export type MS_State = typeof MS_State[keyof typeof MS_State];
export const MS_ServerStates = [MS_State.Plain, MS_State.Frozen, MS_State.Official, MS_State.Identifier];
export type MS_ServerState = typeof MS_ServerStates[number];

export const TournamentState = {
    Pending: 'p',
    Normal: 'n',
    Ongoing: 'o',
    Finished: 'f',
    Preparing: 'r',
    Cancelled: 'c',
    Awarded: 'a',
} as const;
export type TournamentState = typeof TournamentState[keyof typeof TournamentState];

export enum TournamentSubclass {
    GSC = 'g',
    Weekly = 'w',
    Unknown = 'u',
}

export const GSCDefaults = {
    bt: 10000,
    it: 60000,
    et: 240000,
} as const;

export const ColorTemplateNames = ['time', 'bvs', 'stnb', 'ioe', 'thrp', 'path', 'custom'] as const;
export type ColorTemplateName = typeof ColorTemplateNames[number];

export const ColumnChoices = ['state', 'upload_time', 'end_time', 'player', 'software', 'mode', 'level', 'time', 'bv', 'bvs', 'stnb', 'ces', 'cls', 'corr', 'ioe', 'thrp', 'path', 'file_size'] as const;
export type ColumnChoice = typeof ColumnChoices[number];

export const CellChoices = ['time', 'bvs', 'stnb', 'ioe', 'thrp', 'path', 'cls', 'ces', 'iome', 'file_size'] as const;
export type CellChoice = typeof CellChoices[number];

export const PiecewiseColorSchemeName = ['time', 'ioe', 'bvs', 'stnb', 'thrp', 'corr', 'ces', 'cls', 'iome'] as const;
export type PiecewiseColorSchemeName = typeof PiecewiseColorSchemeName[number];

export function getPiecewiseColorSchemeName(stat: PiecewiseColorSchemeName, level?: MS_Level): 'bvs' | 'stnb' | 'ioe' | 'btime' | 'itime' | 'etime' {
    switch (stat) {
        case 'time':
            if (!level) throw new Error('Level must be specified for time');
            // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-assertion
            return `${level}time` as 'btime' | 'itime' | 'etime';
        case 'bvs':
        case 'ces':
        case 'cls':
            return 'bvs';
        case 'ioe':
        case 'thrp':
        case 'corr':
        case 'iome':
            return 'ioe';
        case 'stnb':
            return 'stnb';
    }
}

export const MineracerAccountLinkErrorMessageCategory = ['account_not_found', 'already_linked', 'expired', 'identifier_conflict', 'invalid_device_code', 'link_superseded', 'not_configured', 'pending_start', 'remote_failed', 'requestexception', 'response', 'timeout'] as const;
export type MineracerAccountLinkErrorMessageCategory = typeof MineracerAccountLinkErrorMessageCategory[number];
