<template>
    <div class="log-selector">
        <BaseButton @click="getLogDir">
            {{ t('local.getDirectory') }}
        </BaseButton>
        <ElSelect
            v-model="selectedLog"
            class="log-file-select"
            filterable
            :placeholder="t('local.selectFile')"
            @change="viewLog"
        >
            <ElOption
                v-for="file in fileStats"
                :key="file.name"
                :label="formatLogOption(file)"
                :value="file.name"
            >
                <div class="log-option">
                    <span class="log-option-name">{{ file.name }}</span>
                    <span>{{ formatBytes(file.size) }}</span>
                    <span>{{ formatLogTime(file.mtime) }}</span>
                </div>
            </ElOption>
        </ElSelect>
        <BaseButton :disabled="selectedLog === ''" @click="downloadLog(selectedLog)">
            {{ t('software.download') }}
        </BaseButton>
    </div>
    <div class="log-toolbar">
        <span v-if="selectedLog">
            {{ selectedLog }}
        </span>
        <span>
            {{ t(`local.${streamStatus}`) }}
        </span>
        <BaseButton
            class="log-poll-start"
            :disabled="selectedLog === '' || loadedLog !== selectedLog || isLogPolling"
            @click="startLogPolling"
        >
            {{ t('local.startPolling') }}
        </BaseButton>
        <BaseButton
            class="log-poll-stop"
            :disabled="!isLogPolling"
            @click="stopLogPolling"
        >
            {{ t('local.stopPolling') }}
        </BaseButton>
        <label class="log-poll-interval log-poll-ms">
            {{ t('local.pollInterval') }}
            <ElInputNumber
                v-model="logPollIntervalMs"
                :min="200"
                :max="60000"
                controls-position="right"
                @change="restartLogPolling"
            />
            ms
        </label>
        <label class="log-poll-interval log-tail-bytes">
            {{ t('local.tailBytes') }}
            <ElInputNumber
                v-model="logTailBytes"
                :min="1"
                :max="MAX_TAIL_BYTES"
                controls-position="right"
            />
        </label>
    </div>
    <pre ref="logViewer" class="log-viewer">{{ logNotice ? `${t(logNotice.key, logNotice.params) }\n` : '' }}{{ logContent }}</pre>
</template>

<script lang="ts" setup>
import { ElInputNumber, ElOption, ElSelect } from 'element-plus';
import { nextTick, onBeforeUnmount, onMounted, ref, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { httpErrorNotification } from '@/components/Notifications';
import useCurrentInstance from '@/utils/common/useCurrentInstance';
import { formatBytes } from '@/utils/strings';

interface FileStat {
    name: string;
    size: number;
    mtime: string;
}

interface LogTailResponse {
    content: string;
    offset: number;
    size: number;
    truncated: boolean;
}

interface LogPollResponse {
    content: string;
    offset: number;
    size: number;
    status: 'ok' | 'reset' | 'deleted';
}

defineOptions({ name: 'StaffLogs' });

const DEFAULT_TAIL_BYTES = 65536;
const MAX_TAIL_BYTES = 1048576;
const MAX_VISIBLE_LOG_CHARS = 1048576;

const { proxy } = useCurrentInstance();
const fileStats = ref([] as FileStat[]);
const logContent = ref('');
const logNotice = ref<{ key: string; params: Record<string, number> } | null>(null);
const selectedLog = ref('');
const streamStatus = ref('disconnected');
const logPollIntervalMs = ref(10000);
const logTailBytes = ref(DEFAULT_TAIL_BYTES);
const isLogPolling = ref(false);
const loadedLog = ref('');
const logViewer = useTemplateRef<HTMLElement>('logViewer');
let logPollTimer: number | null = null;
let logPollOffset = 0;
let pollingLog = '';

function closeLogPolling() {
    if (logPollTimer === null) return;
    window.clearInterval(logPollTimer);
    logPollTimer = null;
    isLogPolling.value = false;
}

function stopLogPolling() {
    closeLogPolling();
    if (selectedLog.value !== '') streamStatus.value = 'pollingStopped';
}

function normalizedLogPollIntervalMs() {
    if (!Number.isFinite(logPollIntervalMs.value)) {
        logPollIntervalMs.value = 1000;
    }
    logPollIntervalMs.value = Math.min(Math.max(logPollIntervalMs.value, 200), 60000);
    return logPollIntervalMs.value;
}

function normalizedLogTailBytes() {
    if (!Number.isFinite(logTailBytes.value)) {
        logTailBytes.value = DEFAULT_TAIL_BYTES;
    }
    logTailBytes.value = Math.trunc(Math.min(Math.max(logTailBytes.value, 1), MAX_TAIL_BYTES));
    return logTailBytes.value;
}

function scrollLogViewerToBottom() {
    void nextTick(() => {
        if (logViewer.value === null) return;
        logViewer.value.scrollTop = logViewer.value.scrollHeight;
    });
}

function formatLogTime(mtime: string) {
    return new Date(mtime).toLocaleString(locale.value);
}

function formatLogOption(file: FileStat) {
    return `${file.name} | ${formatBytes(file.size)} | ${formatLogTime(file.mtime)}`;
}

function appendLogContent(content: string) {
    logContent.value += content;
    if (logContent.value.length > MAX_VISIBLE_LOG_CHARS) {
        logContent.value = logContent.value.slice(-MAX_VISIBLE_LOG_CHARS);
    }
    scrollLogViewerToBottom();
}

function applyLogPoll(data: LogPollResponse) {
    if (data.status === 'deleted') {
        streamStatus.value = 'deleted';
        closeLogPolling();
        return;
    }
    if (data.status === 'reset') {
        logContent.value = '';
        logNotice.value = { key: 'local.rotated', params: {} };
    }
    if (data.content !== '') {
        appendLogContent(data.content);
    }
    logPollOffset = data.offset;
}

function pollLogTail() {
    if (pollingLog === '' || !isLogPolling.value) return;
    proxy.$axios.get('/api/common/staff/logpoll', {
        params: {
            filename: pollingLog,
            offset: logPollOffset,
            tail_bytes: normalizedLogTailBytes(),
        },
    }).then((response) => {
        applyLogPoll(response.data as LogPollResponse);
    }).catch((error: unknown) => {
        streamStatus.value = 'pollingFailed';
        closeLogPolling();
        httpErrorNotification(error);
    });
}

function startLogPolling() {
    if (selectedLog.value === '') return;
    closeLogPolling();
    pollingLog = selectedLog.value;
    streamStatus.value = 'polling';
    logPollTimer = window.setInterval(pollLogTail, normalizedLogPollIntervalMs());
    isLogPolling.value = true;
}

function restartLogPolling() {
    if (!isLogPolling.value || pollingLog === '') {
        normalizedLogPollIntervalMs();
        return;
    }
    closeLogPolling();
    streamStatus.value = 'polling';
    logPollTimer = window.setInterval(pollLogTail, normalizedLogPollIntervalMs());
    isLogPolling.value = true;
}

function getLogDir() {
    proxy.$axios.get('/api/common/staff/logs').then(
        function (response) {
            fileStats.value = response.data;
        },
    ).catch(httpErrorNotification);
}

function viewLog(log: string) {
    closeLogPolling();
    streamStatus.value = 'loading';
    pollingLog = '';
    loadedLog.value = '';
    const tailBytes = normalizedLogTailBytes();
    proxy.$axios.get('/api/common/staff/logtail', { params: { filename: log, tail_bytes: tailBytes } }).then(
        function (response) {
            const data = response.data as LogTailResponse;
            logNotice.value = data.truncated ? { key: 'local.truncated', params: { bytes: tailBytes } } : null;
            logContent.value = data.content;
            scrollLogViewerToBottom();
            pollingLog = log;
            logPollOffset = data.offset;
            loadedLog.value = log;
            streamStatus.value = 'loaded';
        },
    ).catch((error: unknown) => {
        streamStatus.value = 'loadFailed';
        httpErrorNotification(error);
    });
}

function downloadLog(log: string) {
    proxy.$axios.get('/api/common/staff/logview', { params: { filename: log }, responseType: 'blob' }).then(
        function (response) {
            const blob = new Blob([response.data], { type: 'application/octet-stream' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = log;
            a.click();
            window.URL.revokeObjectURL(url);
        },
    ).catch(httpErrorNotification);
}

onMounted(getLogDir);
onBeforeUnmount(closeLogPolling);

const i18nMessages = {
    'zh-cn': { local: {
        getDirectory: '获取日志目录',
        selectFile: '选择日志文件',
        startPolling: '开始轮询',
        stopPolling: '停止轮询',
        pollInterval: '轮询间隔',
        tailBytes: '尾部字节',
        disconnected: '未连接',
        pollingStopped: '轮询已停止',
        deleted: '日志文件已删除',
        pollingFailed: '轮询更新失败',
        polling: '轮询更新中',
        loading: '正在加载日志尾部',
        loaded: '已加载，轮询未启动',
        loadFailed: '加载失败',
        rotated: '[日志文件已被截断或轮转，正在从新文件继续读取]',
        truncated: '[仅显示最后 {bytes} 字节]',
    } },
    en: { local: {
        getDirectory: 'Get log directory',
        selectFile: 'Select a log file',
        startPolling: 'Start polling',
        stopPolling: 'Stop polling',
        pollInterval: 'Poll interval',
        tailBytes: 'Tail bytes',
        disconnected: 'Disconnected',
        pollingStopped: 'Polling stopped',
        deleted: 'Log file deleted',
        pollingFailed: 'Polling failed',
        polling: 'Polling',
        loading: 'Loading log tail',
        loaded: 'Loaded, polling not started',
        loadFailed: 'Loading failed',
        rotated: '[Log file truncated or rotated; continuing from the new file]',
        truncated: '[Showing only the last {bytes} bytes]',
    } },
};

const { t, locale } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.log-selector {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.log-file-select {
    width: min(48rem, 70vw);
}

.log-option {
    display: grid;
    grid-template-columns: minmax(10rem, 1fr) 6rem 12rem;
    align-items: center;
    gap: 1rem;
}

.log-option-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.log-toolbar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 1rem;
    margin: 1rem 0 0.5rem;
}

.log-poll-interval {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
}

.log-viewer {
    max-height: 70vh;
    overflow: auto;
    padding: 1rem;
    border: 1px solid var(--ui-border-color);
    border-radius: 4px;
    background: var(--ui-fill-color-light);
    color: var(--ui-text-color-primary);
    font-family: Consolas, Monaco, monospace;
    font-size: 0.875rem;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-all;
}
</style>
