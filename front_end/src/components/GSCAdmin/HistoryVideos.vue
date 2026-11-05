<template>
    <div class="history-video-controls">
        <label>用户 ID <input v-model.number="userId" type="number" min="1" :disabled="busy || participantId !== undefined" data-cy="history-user-id"></label>
        <label data-cy="history-upload-anchor">上传时间锚点 <ElDatePicker v-model="anchor" type="datetime" :disabled="busy || participantId !== undefined" /></label>
        <input type="file" accept=".avf,.evf,.rmv,.mvf" multiple :disabled="busy || participantId !== undefined" aria-label="选择录像" data-cy="history-video-files" @change="selectFiles">
        <ElSelect v-model="selectedIdentifiers" multiple :disabled="busy || participantId !== undefined" placeholder="录像标识" aria-label="录像标识" data-cy="history-identifiers">
            <ElOption v-for="identifier in identifiers" :key="identifier" :label="identifier || '(空标识)'" :value="identifier" />
        </ElSelect>
        <BaseButton :loading="busy" :disabled="!userId || !selectedIdentifiers.length || !anchor" data-cy="history-videos-submit" @click="upload">
            {{ participantId === undefined ? '绑定标识并上传' : bindings.length < selectedIdentifiers.length ? '继续绑定并上传' : '重试失败录像' }}
        </BaseButton>
        <BaseButton :disabled="busy" @click="reset">
            清空
        </BaseButton>
    </div>
    <p v-if="error" role="alert">
        {{ error }}
    </p>
    <ul>
        <li v-for="issue in parseIssues" :key="issue">
            {{ issue }}
        </li>
    </ul>
    <ul data-cy="history-binding-results">
        <li v-for="binding in bindings" :key="binding.identifier">
            {{ binding.identifier || '(空标识)' }}：{{ binding.bound ? '已绑定' : '归属冲突，跳过绑定' }}
        </li>
    </ul>
    <BaseTable v-if="uploads.length" data-cy="history-video-results">
        <template #head>
            <tr><th>文件</th><th>标识</th><th>上传时间</th><th>结果</th></tr>
        </template>
        <tr v-for="entry in uploads" :key="entry.index">
            <td>{{ entry.file.name }}</td><td>{{ entry.identifier }}</td><td>{{ entry.uploadTime.toISOString() }}</td>
            <td>{{ entry.result ? `录像 #${entry.result.id} / ${entry.result.state}` : entry.error || '待上传' }}</td>
        </tr>
    </BaseTable>
</template>

<script setup lang="ts">
import '@/styles/vendors/element-plus.css';
import '@/styles/vendors/element-plus-select.css';
import { ElDatePicker, ElOption, ElSelect } from 'element-plus';
import { computed, onBeforeUnmount, ref, shallowRef } from 'vue';

import { assignHistoryUploadTimes } from './history';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import { bindGSCHistoryIdentifier, prepareGSCHistory, uploadGSCHistoryVideo } from '@/services/gscHistoryService';
import type { IdentifierBinding } from '@/services/gscHistoryService';
import { extract_stat, load_video_file } from '@/utils/fileIO';
import type { VideoAbstractData } from '@/utils/videoabstract';

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

const props = defineProps({ order: { type: Number, required: true }, endTime: { type: Date, required: true } });
const emit = defineEmits<{ imported: [] }>();
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
                entry.error = String(reason);
            }
        }
    } catch (reason) {
        error.value = `${String(reason)}。已完成步骤已保留，请重试未完成步骤。`;
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
