<template>
    <VideoAnalyzer v-model:config="analyzerConfig" v-model:probability-color-scheme="videoPlayerConfig.probabilityColorScheme" v-model:exporting="exporting" :source="source" :loading="loading" :error-message="errorMessage" :title="`${t('local.title')} #${id}`" :filename="`video-${id}`">
        <template #info>
            <slot name="info">
                <WebsiteReplayInfo :id="id" :source="source" :info="info" :loading="infoLoading" :error-message="infoErrorMessage" />
            </slot>
        </template>
    </VideoAnalyzer>
</template>

<script setup lang="ts">
import { inject, ref } from 'vue';
import type { VNode } from 'vue';
import { useI18n } from 'vue-i18n';
import { onBeforeRouteLeave, onBeforeRouteUpdate, routerKey } from 'vue-router';

import { analyzerConfig } from './store';
import { useSiteReplayInfo } from './useSiteReplayInfo';
import { useSiteReplaySource } from './useSiteReplaySource';
import WebsiteReplayInfo from './WebsiteReplayInfo.vue';

import VideoAnalyzer from '@/components/VideoAnalyzer/App.vue';
import { videoPlayerConfig } from '@/store';

const props = defineProps({ id: { type: String, required: true } });
defineSlots<{ info?: () => VNode[] }>();
const exporting = ref(false);
const { source, loading, errorMessage } = useSiteReplaySource(() => props.id);
const { info, loading: infoLoading, errorMessage: infoErrorMessage } = useSiteReplayInfo(() => props.id);
if (inject(routerKey, null)) {
    onBeforeRouteLeave(() => !exporting.value);
    onBeforeRouteUpdate(() => !exporting.value);
}

const i18nMessages = {
    'zh-cn': { local: {
        title: '录像分析',
    } },
    en: { local: {
        title: 'Video analysis',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

