// Wire values match Medal_TextChoices in back_end/saolei/config/text_choices.py.
export const MedalSeries = {
    BREAKTHROUGH: 'b',
    SPEED: 's',
    MASTERY: 'm',
    FLAGLESS_BREAKTHROUGH: 'bn',
    FLAGLESS_SPEED: 'sn',
    FLAGLESS_MASTERY: 'mn',
    FLAGLESS_PRECISION: 'pn',
    FLAGGED_PRECISION: 'pf',
    THREE_FLAGLESS_PRECISION: 'tn',
    THREE_FLAGGED_PRECISION: 'tf',
    REGISTERED: 'r',
    REVIEWED: 'v',
    LEVELS: 'l',
    LEVELS_NF: 'ln',
    MODES: 'o',
    SAOLEI: 'a',
    SHAREHOLDER: 'h',
} as const;
export type MedalSeries = typeof MedalSeries[keyof typeof MedalSeries];

export const MedalKind = {
    PB: 'p',
    COMPOSITE: 'c',
    ONCE: 'o',
    COUNT: 'n',
    BV_SET: 'b',
    CELL_MASK: 'k',
    EVENT_PLACE: 'e',
    GSC_STAT: 's',
    GSC_PLACE: 'g',
    MANUAL: 'm',
    MIN_VIDEO_ID: 'i',
} as const;
export type MedalKind = typeof MedalKind[keyof typeof MedalKind];

export const MedalDirection = {
    ASC: 'a',
    DESC: 'd',
} as const;
export type MedalDirection = typeof MedalDirection[keyof typeof MedalDirection];

export const MedalStyle = {
    ANY: 'a',
    NF: 'n',
    FL: 'f',
} as const;
export type MedalStyle = typeof MedalStyle[keyof typeof MedalStyle];
