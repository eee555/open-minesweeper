<template>
    <span class="button-group" style="display: inline-flex; align-items: center; gap: 0;">
        <BaseTextButton data-cy="zoomout" :aria-label="t('local.zoomOut')" :disabled="zoom <= 0.1" size="small" @click="zoom = zoom - 0.1">
            <BaseIconZoomOut aria-hidden="true" />
        </BaseTextButton>
        <BaseTextButton data-cy="main" size="small" @wheel="handleTextWheel">&nbsp;{{ Math.round(zoom * 100).toString().padStart(3, '&ensp;') }}%&nbsp;</BaseTextButton>
        <BaseTextButton data-cy="zoomin" :aria-label="t('local.zoomIn')" :disabled="zoom >= 4" size="small" @click="zoom = zoom + 0.1">
            <BaseIconZoomIn aria-hidden="true" />
        </BaseTextButton>
    </span>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

import BaseTextButton from '@/components/common/BaseTextButton.vue';
import { BaseIconZoomIn, BaseIconZoomOut } from '@/components/common/icon';

const zoom = defineModel({ type: Number, default: 1 });

function handleTextWheel(event: WheelEvent) {
    event.preventDefault();
    zoom.value = Math.max(Math.min(zoom.value + event.deltaY * -0.001, 4), 0.1);
}

const i18nMessages = {
    'zh-cn': { local: {
        zoomOut: '缩小',
        zoomIn: '放大',
    } },
    en: { local: {
        zoomOut: 'Zoom out',
        zoomIn: 'Zoom in',
    } },
    es: { local: {
        zoomOut: 'Alejar',
        zoomIn: 'Acercar',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
