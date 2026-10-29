<template>
    <span class="text" :class="classes[state]">
        {{ t(`tournament.state.${state}`) }}
    </span>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import { TournamentState } from '@/utils/ms_const';

defineProps({
    state: {
        type: String as PropType<TournamentState>,
        required: true,
    },
});

const { t } = useI18n();

const classes = {
    [TournamentState.Pending]: 'text-primary',
    [TournamentState.Normal]: 'text-info',
    [TournamentState.Preparing]: 'text-warning',
    [TournamentState.Ongoing]: 'text-danger',
    [TournamentState.Finished]: 'text-success',
    [TournamentState.Awarded]: 'text-info',
    [TournamentState.Cancelled]: 'text-info',
} as const;
</script>
