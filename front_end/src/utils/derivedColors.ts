import type { CSSProperties } from 'vue';

import type { DerivedColumn } from '@/services/pbDerivedService';
import { colorThemes } from '@/store/color';
import { getPiecewiseColorSchemeName } from '@/utils/ms_const';

export function derivedColorStyle(column: DerivedColumn, value: number | undefined, colored: boolean): CSSProperties | undefined {
    if (!colored || value === undefined) return undefined;
    if (column.color === 'bvs') return colorThemes.bvs.value.getStyle(value);
    if (column.color === 'bvs-third') return colorThemes.bvs.value.getStyle(value / 3);
    if (column.color === 'time' && column.level !== 'sum') {
        return colorThemes[getPiecewiseColorSchemeName('time', column.level)].value.getStyle(value);
    }
    return undefined;
}
