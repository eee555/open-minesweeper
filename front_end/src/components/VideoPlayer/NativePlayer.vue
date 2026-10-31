<template>
    <div class="native-player">
        <ElResult v-if="loading" icon="info" :title="t('local.loading')" />
        <ElResult v-else-if="errorMessage" icon="error" :title="t('local.loadFailed')" :sub-title="errorMessage" />
        <div v-else-if="video !== null" class="native-player__content">
            <div class="native-player__stage" :class="{ 'native-player__stage--editing': isEditingConfig }">
                <PlayerMainSettings
                    v-if="isEditingPlayerMainConfig"
                    v-model="videoPlayerConfig"
                    class="native-player__player-main-settings"
                />
                <CustomCounter
                    v-else
                    class="native-player__custom-counter"
                    :video="video"
                    :current-ms="currentMs"
                    :config="customCounterConfig"
                />

                <CustomCounterSettings
                    v-if="isEditingCustomCounterConfig"
                    v-model="customCounterConfig"
                    class="native-player__config-editor"
                />
                <PlayerMain
                    v-else
                    :video="video"
                    :current-ms="currentMs"
                    :cursor-position="cursorPosition"
                    :show-probability="videoPlayerConfig.showProbability"
                    :size="videoPlayerConfig.cellSize"
                    :probability-color-scheme="PiecewiseColorScheme.createFromTheme(videoPlayerConfig.probabilityColorScheme)"
                />
            </div>

            <div class="native-player__controls">
                <ProgressBar
                    v-model="currentMs"
                    class="native-player__progress"
                    :duration-ms="durationMs"
                />
                <label class="checkbox">
                    <input v-model="isEditingCustomCounterConfig" class="checkbox-input" type="checkbox">
                    <span>{{ t('local.editCounter') }}</span>
                </label>
                <label class="checkbox">
                    <input v-model="isEditingPlayerMainConfig" class="checkbox-input" type="checkbox">
                    <span>{{ t('local.editPlayerMain') }}</span>
                </label>
                <button
                    type="button"
                    class="base-button square-button" :disabled="videoFile === null"
                    :title="t('local.download')" :aria-label="t('local.download')" @click="downloadBlob(videoFile!, videoFile!.name)"
                >
                    <i class="pi pi-download" aria-hidden="true" />
                </button>
            </div>
        </div>
        <ElResult v-else icon="info" :title="t('local.noVideo')" />
    </div>
</template>

<script setup lang="ts">
import '@/styles/button.css';

import { isAxiosError, isCancel } from 'axios';
import { ElResult } from 'element-plus';
import { computed, onBeforeUnmount, ref, shallowRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import CustomCounter from './CustomCounter.vue';
import CustomCounterSettings from './CustomCounterSettings.vue';
import PlayerMain from './PlayerMain.vue';
import PlayerMainSettings from './PlayerMainSettings.vue';
import ProgressBar from './ProgressBar.vue';
import { customCounterConfig } from './store';

import { fetchReplayFile } from '@/services/replayFileService';
import { videoPlayerConfig } from '@/store';
import { PiecewiseColorScheme } from '@/utils/colors';
import type { AnyVideo } from '@/utils/fileIO';
import { downloadBlob, load_video_file } from '@/utils/fileIO';

const props = defineProps({
    src: { type: String, default: '' },
});

const i18nMessages = {
    'zh-cn': { local: {
        download: '下载录像',
        editCounter: '编辑计数器',
        editPlayerMain: '主面板设置',
        loadFailed: '录像加载失败',
        loading: '正在加载录像',
        noVideo: '没有录像',
    } },
    en: { local: {
        download: 'Download video',
        editCounter: 'Edit counter',
        editPlayerMain: 'Main settings',
        loadFailed: 'Failed to load video',
        loading: 'Loading video',
        noVideo: 'No video',
    } },
};

const { t } = useI18n({ messages: i18nMessages });

const loading = ref(false);
const errorMessage = ref('');
const video = shallowRef<AnyVideo | null>(null);
const currentMs = ref(0);
const durationMs = ref(0);
const isEditingCustomCounterConfig = ref(false);
const isEditingPlayerMainConfig = ref(false);
const cursor = ref({ x: 0, y: 0 });

const isEditingConfig = computed(() => isEditingCustomCounterConfig.value || isEditingPlayerMainConfig.value);

const cursorPosition = computed(() => {
    const pixSize = video.value?.pix_size ?? 0;
    if (pixSize <= 0 || !Number.isFinite(cursor.value.x) || !Number.isFinite(cursor.value.y)) return undefined;
    return {
        rowIndex: cursor.value.y / pixSize,
        columnIndex: cursor.value.x / pixSize,
    };
});

let abortController: AbortController | null = null;
const videoFile = ref<File | null>(null);
watch(() => props.src, (src) => {
    void loadVideo(src);
}, { immediate: true });

watch(currentMs, () => {
    updateVideoState();
});

async function loadVideo(src: string) {
    cleanupVideo();
    errorMessage.value = '';
    loading.value = false;
    currentMs.value = 0;
    durationMs.value = 0;
    abortController?.abort();
    abortController = null;

    if (src === '') return;

    loading.value = true;
    abortController = new AbortController();
    const controller = abortController;

    try {
        const response = await fetchReplayFile(src, { signal: controller.signal, filename: filenameFromSrc(src) });
        if (controller.signal.aborted) return;

        const parsed = load_video_file(response.data, response.filename);
        video.value = parsed;
        durationMs.value = Math.max(0, Math.trunc(parsed.rtime_ms));
        currentMs.value = 0;
        updateVideoState();
        videoFile.value = new File([response.data], response.filename, {
            type: 'application/octet-stream',
        });
    } catch (error) {
        if (!controller.signal.aborted && !isCancel(error)) {
            reportLoadError(error);
        }
    } finally {
        if (!controller.signal.aborted) loading.value = false;
    }
}

function updateVideoState() {
    const currentVideo = video.value;
    if (currentVideo === null) return;

    // Let the library clamp to the final event without rounding the time offset below it.
    currentVideo.current_time = currentMs.value >= durationMs.value ? Infinity : currentMs.value / 1000;
    cursor.value = currentVideo.x_y;
}

function filenameFromSrc(src: string) {
    const url = new URL(src, window.location.href);
    return url.searchParams.get('id') ?? '';
}

function reportLoadError(error: unknown) {
    errorMessage.value = formatLoadError(error);
}

function formatLoadError(error: unknown) {
    if (isAxiosError(error) && error.response !== undefined) {
        return `${error.response.status} ${error.response.statusText}`.trim();
    }
    if (error instanceof Error && error.message !== '') return error.message;
    return String(error);
}

function cleanupVideo() {
    videoFile.value = null;
    video.value?.free();
    video.value = null;
}

onBeforeUnmount(() => {
    abortController?.abort();
    cleanupVideo();
});
</script>

<style scoped>
.native-player {
    min-width: min(92vw, 520px);
    max-width: calc(95vw - 50px);
    overflow: hidden;
}

.native-player__content {
    display: flex;
    flex-direction: column;
    gap: 12px;
    width: 100%;
    min-width: 0;
    max-width: calc(95vw - 50px);
    max-height: calc(100vh - 170px);
    overflow: hidden;
}

.native-player__controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
    min-width: 0;
}

.native-player__stage {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    width: 100%;
    min-width: 0;
    max-width: 100%;
    overflow-x: auto;
    overflow-y: hidden;
}

.native-player__stage--editing {
    align-items: stretch;
    justify-content: flex-start;
}

.native-player__stage--editing .native-player__custom-counter {
    align-self: center;
}

.native-player__player-main-settings {
    align-self: center;
}

.native-player__config-editor {
    flex: 0 0 auto;
    align-self: stretch;
    max-height: calc(100vh - 290px);
}

@media (width <= 720px) {
    .native-player__stage {
        flex-direction: column;
        align-items: center;
    }

    .native-player__stage--editing {
        align-items: flex-start;
    }
}

.native-player__progress {
    flex: 1 1 260px;
    min-width: 160px;
}
</style>
