<template>
    <div style="text-align: center;">
        <BaseFileInput accept=".avf,.evf,.rmv,.mvf" :disabled="!canSubmitReplays || isParsing || isUploading" :style="{ height: uploadQueue.length > 0 ? 'auto' : '300px' }" @add="handleFileChange">
            <FileInputContent :can-submit-replays="canSubmitReplays" />
            <template v-if="canSubmitReplays" #options>
                <FileInputOptions />
            </template>
        </BaseFileInput>
    </div>
    <ToolBar v-if="uploadQueue.length > 0 && canSubmitReplays" v-model:stopping="pleaseStopUploading" :selected="selectedQueue.length" :total="uploadQueue.length" :processing="isWaiting" @upload="uploadSelected" @remove="removeSelected" />
    <Progress :parser-progress="parserProgress" :upload-progress="uploadProgress" />
    <Table v-if="uploadQueue.length > 0" v-model:selected-rows="selectedQueue" v-loading="isWaiting" :data="uploadQueue" />
</template>

<script setup lang="ts">
import { vLoading } from 'element-plus';
import { computed, ref } from 'vue';

import FileInputContent from './FileInputContent.vue';
import FileInputOptions from './FileInputOptions.vue';
import Progress from './Progress.vue';
import Table from './Table.vue';
import ToolBar from './ToolBar.vue';
import type { UploadEntry } from './utils';
import { fileCollide, isUploadableStatus, prepareUploadEntry, uploadEntry } from './utils';

import BaseFileInput from '@/components/common/BaseFileInput.vue';
import { local } from '@/store';
import { ArrayUtils } from '@/utils/arrays';
import type { VideoAbstract } from '@/utils/videoabstract';

const props = defineProps({
    canSubmitReplays: { type: Boolean, default: false },
});

const emit = defineEmits<{
    onUpload: [video: VideoAbstract];
}>();

const uploadQueue = ref<UploadEntry[]>([]);
const selectedQueue = ref<UploadEntry[]>([]);

const parserProgress = ref({
    total: 0,
    parsed: 0,
});
const isParsing = computed(() => parserProgress.value.total != parserProgress.value.parsed);

const uploadProgress = ref({
    total: 0,
    uploaded: 0,
    failed: 0,
});
const isUploading = computed(() => uploadProgress.value.uploaded + uploadProgress.value.failed != uploadProgress.value.total);

const isWaiting = computed(() => isParsing.value || isUploading.value);

const pleaseStopUploading = ref(false);

async function handleFileChange(files: File[]) {
    if (!props.canSubmitReplays || ArrayUtils.isEmpty(files)) return;

    parserProgress.value.total = files.length;
    parserProgress.value.parsed = 0;

    const uploadQueueTemp: UploadEntry[] = [];

    for (const file of files) {
        const entry = await upload_prepare(file);
        const exists = uploadQueue.value.some((e) => fileCollide(e, entry)) || uploadQueueTemp.some((e) => fileCollide(e, entry));
        if (!exists) {
            if (local.value.autoUploadAfterParse) {
                await forceUpload(entry);
            }
            if (entry.status !== 'success' || !local.value.autoRemoveAfterUpload) {
                uploadQueueTemp.push(entry);
            }
        }
        parserProgress.value.parsed += 1;
    }

    uploadQueue.value = [...uploadQueueTemp, ...uploadQueue.value];
}

const forceUpload = async (entry: UploadEntry) => {
    if (!props.canSubmitReplays) return entry;
    try {
        await uploadEntry(entry, 200);
        if (entry.status === 'success' && entry.stat !== undefined) {
            emit('onUpload', entry.stat);
        }
    } catch (_error) {
        console.error(_error);
    }
    return entry;
};

async function upload_prepare(file: File): Promise<UploadEntry> {
    return prepareUploadEntry(file);
}

async function uploadSelected() {
    if (!props.canSubmitReplays) return;
    uploadProgress.value.total = selectedQueue.value.length;
    uploadProgress.value.uploaded = 0;
    uploadProgress.value.failed = 0;
    pleaseStopUploading.value = false;

    const selectedQueueTemp = [...selectedQueue.value];
    const uploadQueueTemp = [...uploadQueue.value];
    for (const entry of selectedQueue.value) {
        if (pleaseStopUploading.value) {
            uploadProgress.value.total = uploadProgress.value.uploaded + uploadProgress.value.failed;
            break;
        }

        if (isUploadableStatus(entry.status)) {
            await forceUpload(entry);
            if (entry.status === 'success') {
                const selectedIndex = selectedQueueTemp.indexOf(entry);
                selectedQueueTemp.splice(selectedIndex, 1);
                const uploadIndex = uploadQueueTemp.indexOf(entry);
                uploadQueueTemp.splice(uploadIndex, 1);
                uploadProgress.value.uploaded += 1;
            } else {
                uploadProgress.value.failed += 1;
            }
        } else {
            uploadProgress.value.failed += 1;
        }
    }

    if (local.value.autoRemoveAfterUpload) {
        selectedQueue.value = selectedQueueTemp;
        uploadQueue.value = uploadQueueTemp;
    }
}

function removeSelected() {
    for (const entry of selectedQueue.value) {
        const index = uploadQueue.value.indexOf(entry);
        uploadQueue.value.splice(index, 1);
    }
    selectedQueue.value.length = 0;
}
</script>
