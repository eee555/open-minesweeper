<template>
    <img style="width: 16px; height: 16px" :src="iconSrc" :title="t(`common.software.${software}`)">
</template>

<script setup lang="ts">
import '@/styles/text.css';

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
    }
});
</script>
