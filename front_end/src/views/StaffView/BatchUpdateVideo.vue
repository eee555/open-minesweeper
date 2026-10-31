<template>
    {{ t('local.startId') }}<ElInputNumber v-model="startid" />&nbsp;
    {{ t('local.endId') }}<ElInputNumber v-model="endid" />&nbsp;
    {{ t('staff.batch.size') }}<ElInputNumber v-model="batchsize" />&nbsp;
    <BaseButton :disabled="working" @click="startBatchUpdate">
        {{ t('button.start') }}
    </BaseButton>
    <BaseButton :disabled="!working" @click="stopBatchUpdate">
        {{ t('button.stop') }}
    </BaseButton><br>
    {{ t('staff.batch.help') }}
    <span v-for="(log, index) in logList" :key="index" :style="{ display: 'block' }">
        {{ t(log.key, log.params) }}
    </span>
</template>

<script setup lang="ts">
import { ElInputNumber } from 'element-plus';
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import useCurrentInstance from '@/utils/common/useCurrentInstance';

const { proxy } = useCurrentInstance();

const startid = ref(1);
const endid = ref(1000);
const batchsize = ref(100);

const working = ref(false);
const logList = ref<{ key: string; params: Record<string, string | number> }[]>([]);

async function startBatchUpdate() {
    working.value = true;
    for (let i = startid.value; i <= endid.value; i += batchsize.value) {
        if (!working.value) break;
        const start = i;
        const end = Math.min(i + batchsize.value - 1, endid.value);
        logList.value.push({ key: 'staff.batch.processing', params: { time: new Date().toISOString(), start, end } });
        await proxy.$axios.post('video/update/batch/', { startid: start, endid: end }).then(
            function ({ data }: { data: { successCount: number; errorList: number[] } }) {
                logList.value.push({ key: 'staff.batch.completed', params: { start, end, success: data.successCount, failed: data.errorList.length } });
                if (data.errorList.length > 0) {
                    logList.value.push({ key: 'local.failedIds', params: { ids: data.errorList.join(', ') } });
                }
            },
        ).catch(function (error: unknown) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            logList.value.push({ key: 'staff.batch.error', params: { start, end, error: errorMessage } });
        });
    }
    working.value = false;
}

function stopBatchUpdate() {
    working.value = false;
}

const i18nMessages = {
    'zh-cn': { local: {
        startId: '录像开始 ID',
        endId: '录像结束 ID',
        failedIds: '失败的录像为：{ids}',
    } },
    en: { local: {
        startId: 'Starting video ID',
        endId: 'Ending video ID',
        failedIds: 'Failed video IDs: {ids}',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
