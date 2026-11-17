<template>
    <Tippy interactive trigger="click" placement="bottom-end" :append-to="appendToBody">
        <button type="button" class="video-list__filter-button" :aria-label="filterLabel" :title="filterLabel" :data-cy="`video-filter-${choice}`">
            <i class="pi" :class="active ? 'pi-filter-fill' : 'pi-filter'" aria-hidden="true" />
        </button>
        <template #content>
            <div class="card card-small video-list__filter-menu" data-cy="video-filter-menu" @click.stop>
                <VideoStateFilter v-if="choice === 'state'" v-model="stateModel" :include-local="includeLocal" class="checkbox-buttons--compact" />
                <SoftwareFilter v-else-if="choice === 'software'" v-model="softwareModel" />
                <div v-else-if="choice === 'level'" class="checkbox-buttons--compact radio-buttons" role="group" :aria-label="t('prop.level')" data-cy="video-filter-level-options">
                    <label v-for="option in levelOptions" :key="option.value ?? 'all'" class="radio-button">
                        <input v-model="levelModel" class="radio-button-input" type="radio" :value="option.value">
                        <span class="radio-button-content">{{ option.label }}</span>
                    </label>
                </div>
                <div v-else-if="choice === 'mode'" class="checkbox-buttons checkbox-buttons--compact" role="group" :aria-label="t('prop.mode')" data-cy="video-filter-mode">
                    <label v-for="mode in modeOptions" :key="mode" class="checkbox-button">
                        <input v-model="modeModel" class="checkbox-button-input" type="checkbox" :value="mode">
                        <span class="checkbox-button-content">{{ t(`mode.code${mode}`) }}</span>
                    </label>
                </div>
            </div>
        </template>
    </Tippy>
</template>

<script setup lang="ts">
import 'primeicons/primeicons.css';

import type { PropType } from 'vue';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { Tippy } from 'vue-tippy';

import type { VideoListFilters } from './videoListData';
import { CUSTOM_LEVEL_FILTER, isColumnFilterActive } from './videoListData';

import SoftwareFilter from '@/components/Filters/SoftwareFilter.vue';
import VideoStateFilter from '@/components/Filters/VideoStateFilter.vue';
import type { ColumnChoice, MS_Software } from '@/utils/ms_const';
import { MS_Levels, MS_Mode } from '@/utils/ms_const';

const props = defineProps({
    choice: { type: String as PropType<ColumnChoice>, required: true },
    filters: { type: Object as PropType<VideoListFilters>, required: true },
    includeLocal: { type: Boolean, default: false },
});
const emit = defineEmits<{
    change: [patch: Partial<VideoListFilters>];
}>();

const appendToBody = () => document.body;
const modeOptions = Object.values(MS_Mode);

const stateModel = computed<string[]>({
    get: () => props.filters.state,
    set: (value) => {
        emit('change', { state: value });
    },
});
const softwareModel = computed<MS_Software[]>({
    get: () => props.filters.software,
    set: (value) => {
        emit('change', { software: value });
    },
});
const levelModel = computed<string | null>({
    get: () => props.filters.level,
    set: (value) => {
        emit('change', { level: value });
    },
});
const modeModel = computed<string[]>({
    get: () => props.filters.mode,
    set: (value) => {
        emit('change', { mode: value });
    },
});

const i18nMessages = {
    'zh-cn': { local: {
        filter: '筛选',
        all: '全部',
        custom: '自定义等级',
    } },
    en: { local: {
        filter: 'Filter',
        all: 'All',
        custom: 'Custom level',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
const levelOptions = computed(() => [
    { value: null, label: t('local.all') },
    ...MS_Levels.map((level) => ({ value: level, label: t(`level.${level}`) })),
    { value: CUSTOM_LEVEL_FILTER, label: t('local.custom') },
]);
const filterLabel = computed(() => `${t('local.filter')} ${t(`prop.${props.choice}`)}`);
const active = computed(() => isColumnFilterActive(props.choice, props.filters, props.includeLocal));
</script>
