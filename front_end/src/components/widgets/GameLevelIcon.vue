<template>
    <span class="text" :title="title">{{ label }}</span>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { CustomLevel } from '@/utils/customlevel';
import type { MS_Level } from '@/utils/ms_const';
import { isStandardLevel } from '@/utils/ms_const';

const props = defineProps({
    level: {
        type: [String, Object] as PropType<MS_Level | CustomLevel>,
        required: true,
    },
});

const titles = {
    b: '8x8/10',
    i: '16x16/40',
    e: '30x16/99',
};

const { t } = useI18n();

const title = computed(() => {
    if (props.level instanceof CustomLevel) return props.level.toString();
    return titles[props.level];
});

const label = computed(() => {
    if (props.level instanceof CustomLevel) {
        return t('level.c', {
            column: props.level.column,
            mine: props.level.mine,
            row: props.level.row,
        });
    }
    if (isStandardLevel(props.level)) return t(`level.${props.level}`);
    return t('level.c');
});
</script>
