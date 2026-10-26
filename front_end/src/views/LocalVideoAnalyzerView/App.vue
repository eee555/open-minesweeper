<template>
    <VideoAnalyzer v-model:config="config" v-model:probability-color-scheme="probabilityColorScheme" v-model:exporting="exporting" :source="source" :loading="loading" :error-message="displayError">
        <template #info>
            <BaseFileInput class="local-analyzer__file" accept=".avf,.evf,.mvf,.rmv,.AVF,.EVF,.MVF,.RMV" :multiple="false" :disabled="exporting" @add="selectFiles">
                <span>{{ t('local.choose') }}</span>
                <span v-if="filename" class="local-analyzer__filename">{{ filename }}</span>
            </BaseFileInput>
            <div class="local-analyzer__info-actions">
                <div class="local-analyzer__notices">
                    <details class="local-analyzer__readme">
                        <summary>README · {{ t('local.readme') }}</summary>
                        <pre>{{ offlineReadme }}</pre>
                    </details>
                    <details class="local-analyzer__copyright">
                        <summary>COPYRIGHT · {{ t('local.copyright') }}</summary>
                        <pre>{{ offlineCopyright }}</pre>
                    </details>
                </div>
                <div class="local-analyzer__meta">
                    <div class="local-analyzer__identity">
                        <img class="local-analyzer__icon" :src="analyzerIcon" alt="" width="24" height="24">
                        <span class="local-analyzer__version">{{ t('software.version') }} v{{ analyzerVersion.version }}</span>
                    </div>
                    <BaseButton class="local-analyzer__language" size="small" :title="t('local.switchLanguage')" :aria-label="t('local.switchLanguage')" @click="toggleLanguage">
                        {{ globalLocale.startsWith('zh') ? 'English' : '中文' }}
                    </BaseButton>
                </div>
            </div>
        </template>
    </VideoAnalyzer>
</template>

<script setup lang="ts">
import { useLocalStorage } from '@vueuse/core';
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import offlineCopyright from '../../../local-analyzer/COPYRIGHT.txt?raw';
import offlineReadme from '../../../local-analyzer/README.txt?raw';
import analyzerVersion from '../../../local-analyzer/version.json';

import { useLocalReplaySource } from './useLocalReplaySource';

import analyzerIcon from '@/assets/video-analyzer.svg?inline';
import BaseButton from '@/components/common/BaseButton.vue';
import BaseFileInput from '@/components/common/BaseFileInput.vue';
import VideoAnalyzer, { defaultAnalyzerConfig } from '@/components/VideoAnalyzer';
import { local } from '@/store/local';

const { locale: globalLocale } = useI18n({ useScope: 'global' });

const config = useLocalStorage('local-video-analyzer-config', defaultAnalyzerConfig(), { mergeDefaults: true });
const probabilityColorScheme = useLocalStorage('local-video-analyzer-probability', { colors: ['#15803d', '#0f766e', '#2563eb', '#b45309', '#dc2626', '#7f1d1d'], thresholds: [10, 25, 50, 75, 90] }, { mergeDefaults: true });
const exporting = ref(false);
const { source, filename, loading, errorMessage, selectFiles: readFiles } = useLocalReplaySource();
const displayError = computed(() => (['oneFileOnly', 'unsupportedFormat'].includes(errorMessage.value) ? t(`local.${errorMessage.value}`) : errorMessage.value));

function selectFiles(files: File[]) {
    if (!exporting.value) void readFiles(files);
}

function toggleLanguage() {
    const language = globalLocale.value.startsWith('zh') ? 'en' : 'zh-cn';
    globalLocale.value = language;
    local.value.language = language;
    document.documentElement.lang = language;
}

const i18nMessages = {
    'zh-cn': { local: {
        choose: '选择或拖入一份录像文件（EVF / AVF / MVF / RMV）',
        readme: '使用说明',
        copyright: '版权声明',
        switchLanguage: '切换到英文',
        oneFileOnly: '每次只能选择一份录像文件',
        unsupportedFormat: '不支持的录像格式，请选择 EVF、AVF、MVF 或 RMV',
    } },
    en: { local: {
        choose: 'Choose or drop one replay file (EVF / AVF / MVF / RMV)',
        readme: 'Usage',
        copyright: 'Copyright',
        switchLanguage: 'Switch to Chinese',
        oneFileOnly: 'Select only one replay file at a time',
        unsupportedFormat: 'Unsupported replay format. Choose EVF, AVF, MVF or RMV',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.local-analyzer__file {
    padding: 0;
}
.local-analyzer__filename {
    overflow-wrap: anywhere;
}
.local-analyzer__info-actions {
    display: flex;
    align-items: flex-start;
    gap: 4px;
}
.local-analyzer__meta {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 4px;
    flex-shrink: 0;
}
.local-analyzer__version {
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
}
.local-analyzer__identity {
    display: flex;
    align-items: center;
    gap: 4px;
}
.local-analyzer__icon {
    flex-shrink: 0;
    object-fit: contain;
}
.local-analyzer__notices {
    flex: 1;
    min-width: 0;
    max-height: min(32vh, 240px);
    overflow: auto;
}
.local-analyzer__notices summary {
    cursor: pointer;
}
.local-analyzer__notices pre {
    margin: 4px 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    font: inherit;
}
</style>
