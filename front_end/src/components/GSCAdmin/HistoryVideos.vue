<template>
    <div class="history-video-controls">
        <label>{{ t('local.userId') }} <input v-model.number="userId" type="number" min="1" :disabled="busy || participantId !== undefined" data-cy="history-user-id"></label>
        <label data-cy="history-upload-anchor">{{ t('local.anchor') }} <ElDatePicker v-model="anchor" type="datetime" :disabled="busy || participantId !== undefined" /></label>
        <input type="file" accept=".avf,.evf,.rmv,.mvf" multiple :disabled="busy || participantId !== undefined" :aria-label="t('local.chooseFiles')" data-cy="history-video-files" @change="selectFiles">
        <ElSelect v-model="selectedIdentifiers" multiple :disabled="busy || participantId !== undefined" :placeholder="t('local.identifiers')" :aria-label="t('local.identifiers')" data-cy="history-identifiers">
            <ElOption v-for="identifier in identifiers" :key="identifier" :label="identifier || t('local.emptyIdentifier')" :value="identifier" />
        </ElSelect>
        <BaseButton :loading="busy" :disabled="!userId || !selectedIdentifiers.length || !anchor" data-cy="history-videos-submit" @click="upload">
            {{ participantId === undefined ? t('local.bindAndUpload') : bindings.length < selectedIdentifiers.length ? t('local.resumeBinding') : t('local.retry') }}
        </BaseButton>
        <BaseButton :disabled="busy" @click="reset">
            {{ t('local.clear') }}
        </BaseButton>
    </div>
    <p v-if="error" role="alert">
        {{ error }}<br>
        {{ t('local.retryPending') }}
    </p>
    <ul>
        <li v-for="issue in parseIssues" :key="issue">
            {{ issue }}
        </li>
    </ul>
    <ul data-cy="history-binding-results">
        <li v-for="binding in bindings" :key="binding.identifier">
            {{ binding.identifier || t('local.emptyIdentifier') }}：{{ binding.bound ? t('local.bound') : t('local.conflict') }}
        </li>
    </ul>
    <BaseTable v-if="uploads.length" data-cy="history-video-results">
        <template #head>
            <tr><th>{{ t('local.file') }}</th><th>{{ t('local.identifier') }}</th><th>{{ t('local.uploadTime') }}</th><th>{{ t('local.result') }}</th></tr>
        </template>
        <tr v-for="entry in uploads" :key="entry.index">
            <td>{{ entry.file.name }}</td><td>{{ entry.identifier }}</td><td>{{ entry.uploadTime.toISOString() }}</td>
            <td>{{ entry.result ? t('local.replayResult', { id: entry.result.id, state: entry.result.state }) : entry.error || t('local.pending') }}</td>
        </tr>
    </BaseTable>
</template>

<script setup lang="ts">
import '@/styles/vendors/element-plus.css';
import '@/styles/vendors/element-plus-select.css';
import { ElDatePicker, ElOption, ElSelect } from 'element-plus';
import { computed, onBeforeUnmount, ref, shallowRef } from 'vue';
import { useI18n } from 'vue-i18n';

import { assignHistoryUploadTimes } from './history';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import { historyErrorText } from '@/i18n/historyErrorText';
import { bindGSCHistoryIdentifier, prepareGSCHistory, uploadGSCHistoryVideo } from '@/services/gscHistoryService';
import type { IdentifierBinding } from '@/services/gscHistoryService';
import { extract_stat, load_video_file } from '@/utils/fileIO';
import type { VideoAbstractData } from '@/utils/videoabstract';

const props = defineProps({ order: { type: Number, required: true }, endTime: { type: Date, required: true } });
const emit = defineEmits<{ imported: [] }>();
const i18nMessages = {
    'zh-cn': { local: {
        replayResult: '录像 #{id} / {state}',
        retryPending: '已完成步骤已保留，请重试未完成步骤。',
        conflict: '归属冲突，跳过绑定',
        bindAndUpload: '绑定标识并上传',
        resumeBinding: '继续绑定并上传',
        anchor: '上传时间锚点',
        retry: '重试失败录像',
        userId: '用户 ID',
        emptyIdentifier: '(空标识)',
        chooseFiles: '选择录像',
        identifiers: '录像标识',
        uploadTime: '上传时间',
        bound: '已绑定',
        pending: '待上传',
        clear: '清空',
        file: '文件',
        identifier: '标识',
        result: '结果',
    } },
    en: { local: {
        replayResult: 'Replay #{id} / {state}',
        retryPending: 'Completed steps were saved. Retry the remaining steps.',
        conflict: 'Ownership conflict, skipped',
        bindAndUpload: 'Link identifiers and upload',
        resumeBinding: 'Continue linking and upload',
        anchor: 'Reference upload time',
        retry: 'Retry failed uploads',
        userId: 'User ID',
        emptyIdentifier: '(empty identifier)',
        chooseFiles: 'Choose replay files',
        identifiers: 'Replay identifiers',
        uploadTime: 'Upload time',
        bound: 'Linked',
        pending: 'Pending upload',
        clear: 'Clear',
        file: 'File',
        identifier: 'Identifier',
        result: 'Result',
    } },
    es: { local: {
        replayResult: 'Repetición #{id} / {state}',
        retryPending: 'Se han guardado los pasos completados. Reintenta los pendientes.',
        conflict: 'Conflicto de titularidad. Se omitió la vinculación',
        bindAndUpload: 'Vincular identificadores y subir',
        resumeBinding: 'Continuar la vinculación y subir',
        anchor: 'Fecha de referencia para la subida',
        retry: 'Reintentar las subidas fallidas',
        userId: 'ID de usuario',
        emptyIdentifier: '(identificador vacío)',
        chooseFiles: 'Seleccionar repeticiones',
        identifiers: 'Identificadores de las repeticiones',
        uploadTime: 'Fecha de subida',
        bound: 'Vinculado',
        pending: 'Pendiente de subida',
        clear: 'Vaciar',
        file: 'Archivo',
        identifier: 'Identificador',
        result: 'Resultado',
    } },
};
const { t } = useI18n({ messages: i18nMessages });

interface Replay {
    index: number;
    file: File;
    identifier: string;
    endTime: Date;
    timems: number;
}
interface Upload extends Replay {
    uploadTime: Date;
    result?: VideoAbstractData;
    error?: string;
}

const userId = ref<number>();
const anchor = ref<Date | null>(new Date(props.endTime));
const replays = shallowRef<Replay[]>([]);
const selectedIdentifiers = ref<string[]>([]);
const identifiers = computed(() => [...new Set(replays.value.map((replay) => replay.identifier))]);
const parseIssues = ref<string[]>([]);
const bindings = ref<IdentifierBinding[]>([]);
const uploads = ref<Upload[]>([]);
const participantId = ref<number>();
const busy = ref(false);
const error = ref('');
let stopped = false;
onBeforeUnmount(() => {
    stopped = true;
});

function reset() {
    replays.value = [];
    selectedIdentifiers.value = [];
    parseIssues.value = [];
    bindings.value = [];
    uploads.value = [];
    participantId.value = undefined;
    error.value = '';
}

async function selectFiles(event: Event) {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    input.value = '';
    reset();
    busy.value = true;
    const parsed: Replay[] = [];
    try {
        for (const [index, file] of files.entries()) {
            try {
                const video = load_video_file(await file.arrayBuffer(), file.name.toLowerCase());
                try {
                    if (!video.is_completed) throw new Error('Incomplete replay');
                    const stat = extract_stat(video);
                    if (!stat.end_time || !Number.isFinite(stat.end_time.getTime()) || !Number.isSafeInteger(stat.timems) || stat.timems <= 0) throw new Error('Invalid end time or duration');
                    parsed.push({ index, file, identifier: video.player_identifier, endTime: stat.end_time, timems: stat.timems });
                } finally {
                    video.free();
                }
            } catch (reason) {
                parseIssues.value.push(`${file.name}: ${String(reason)}`);
            }
        }
        replays.value = parsed;
        selectedIdentifiers.value = [...identifiers.value];
    } finally {
        busy.value = false;
    }
}

async function upload() {
    if (busy.value || userId.value === undefined || userId.value <= 0 || !Number.isSafeInteger(userId.value) || anchor.value === null || !selectedIdentifiers.value.length) return;
    busy.value = true;
    error.value = '';
    try {
        if (participantId.value === undefined) {
            uploads.value = assignHistoryUploadTimes(replays.value.filter((replay) => selectedIdentifiers.value.includes(replay.identifier)), anchor.value);
            const prepared = await prepareGSCHistory(props.order, userId.value);
            participantId.value = prepared.id;
        }
        for (const identifier of selectedIdentifiers.value) {
            if (stopped) return;
            if (bindings.value.some((binding) => binding.identifier === identifier)) continue;
            bindings.value.push(await bindGSCHistoryIdentifier(participantId.value, identifier));
        }
        for (const entry of uploads.value) {
            if (stopped) break;
            if (entry.result) continue;
            try {
                entry.result = await uploadGSCHistoryVideo(participantId.value, entry.file, entry.uploadTime);
                entry.error = undefined;
            } catch (reason) {
                entry.error = historyErrorText(reason);
            }
        }
    } catch (reason) {
        error.value = historyErrorText(reason);
    } finally {
        busy.value = false;
        emit('imported');
    }
}
</script>

<style scoped>
.history-video-controls {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
}
.history-video-controls .el-select {
    width: 320px;
    max-width: 100%;
}
</style>
