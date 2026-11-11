
const ArbiterStatsAutoColorTemplate = [
    'rgba(255,255,255,0)',
    '#999999', '#CCCCCC', '#CC99FF', '#CCCCFF',
    '#996666', '#CCCC00', '#CC6666', '#CC9900',
    '#99CC33', '#CCFFCC', '#00CC00', '#00FF99',
    '#33CCFF', '#66FFFF', '#0099FF', '#0099CC',
    '#FFCC00', '#FFCC99', '#FF9900', '#FFFF66',
    '#FF99FF', '#FFCCFF', '#FF6699', '#FF9999',
    '#99FF99', '#339933', '#9966FF', '#FFFF99',
    '#FF3366',
] as const;

const ArbiterStatsAutoValueTemplate = [
    0.01,
    0.5, 1, 1.5, 2,
    2.25, 2.5, 2.75, 3,
    3.25, 3.5, 3.75, 4,
    4.25, 4.5, 4.75, 5,
    5.25, 5.5, 5.75, 6,
    6.25, 6.5, 6.75, 7,
    7.5, 8, 9, 10,
] as const;

const ArbiterStatsAutoValueTemplate_IOE = [
    0.01,
    0.5, 0.6, 0.7, 0.8,
    0.9, 0.95, 1, 1.05,
    1.1, 1.15, 1.2, 1.25,
    1.3, 1.35, 1.4, 1.45,
    1.5, 1.55, 1.6, 1.65,
    1.7, 1.75, 1.8, 1.85,
    1.9, 1.95, 2, 2.1,
] as const;

export const colorSchemeTemplates = {
    ArbiterStatsAuto: {
        bvs: {
            thresholds: ArbiterStatsAutoValueTemplate,
            colors: ArbiterStatsAutoColorTemplate,
        },
        stnb: {
            thresholds: ArbiterStatsAutoValueTemplate.map((v) => v * 25),
            colors: ArbiterStatsAutoColorTemplate,
        },
        ioe: {
            thresholds: ArbiterStatsAutoValueTemplate_IOE,
            colors: ArbiterStatsAutoColorTemplate,
        },
        btime: {
            thresholds: ArbiterStatsAutoValueTemplate.map((v) => 12 - v * 2).reverse(),
            colors: ArbiterStatsAutoColorTemplate.toReversed(),
        },
        itime: {
            thresholds: ArbiterStatsAutoValueTemplate.map((v) => 30 - v * 4).reverse(),
            colors: ArbiterStatsAutoColorTemplate.toReversed(),
        },
        etime: {
            thresholds: ArbiterStatsAutoValueTemplate.map((v) => 90 - v * 10).reverse(),
            colors: ArbiterStatsAutoColorTemplate.toReversed(),
        },
        grade: {
            thresholds: [100, 60, 55, 50, 45, 40, 35, 30],
            colors: ['rgba(255,255,255,0)', '#808080', '#00B0F0', '#005696', '#FFC000', '#A65C12', '#14D2A0', '#0B7B5E', '#CCFF66'],
        },
    },
} as const;
