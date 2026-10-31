<template>
    <div class="cell">
        <span class="text-regular">{{ t(`level.short${level}`) }}</span>
    </div>
    <div v-for="i in count" class="cell">
        <span class="text-regular">{{ i }}</span>
    </div>
    <div class="cell">
        <span class="text-regular">{{ t('score.sum') }}</span>
    </div>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import type { MS_Level } from '@/utils/ms_const';

defineProps({
    level: {
        type: String as PropType<MS_Level | ''>,
        default: '',
    },
    count: {
        type: Number,
        default: 0,
    },
});

const { t } = useI18n();
</script>

<style lang="less" scoped>

@import './cell.less';

</style>
