<template>
    <img v-if="iconSrc" style="width: 16px; height: 16px" :src="iconSrc" :title="t(`software.${software}`)">
    <span v-else class="software-fallback" :title="t(`software.${software}`)">{{ t(`software.${software}`) }}</span>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { local } from '@/store';
import { ArbiterIcon, Clone07Icon, MetasweeperIcon, ViennaIconLegacy, ViennaIconNew } from '@/utils/assets';
import type { MS_Software } from '@/utils/ms_const';

const props = defineProps({
    software: {
        type: String as PropType<MS_Software>,
        required: true,
    },
});

const { t } = useI18n();

const iconSrc = computed(() => {
    switch (props.software) {
        case 'a': return ArbiterIcon;
        case 'e': return MetasweeperIcon;
        case 'r': return local.value.vienna_logo_legacy ? ViennaIconLegacy : ViennaIconNew;
        case 'm': return Clone07Icon;
        case 'x': return null;
    }
});
</script>

<style scoped>
.software-fallback {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 16px;
    height: 16px;
    font-size: 9px;
    font-weight: 600;
    line-height: 1;
}
</style>
