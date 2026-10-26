<template>
    <ElTabPane v-loading="loadingStatus == QueueRefreshStatus.Refreshing" class="bottom_tabs" lazy name="newest">
        <template #label>
            {{ t('home.latestScore') }}&nbsp;
            <span v-if="loadingStatus == QueueRefreshStatus.CoolingDown" class="text-success">
                <BaseIconTick />
            </span>
            <BaseTextButton
                v-else-if="isActive" underline="never"
                :disabled="loadingStatus != QueueRefreshStatus.Available" :aria-label="t('action.getVideoModel')"
                style="vertical-align: baseline;" @keydown.stop @click="refresh"
            >
                <BaseIconRefresh />
            </BaseTextButton>
        </template>
        <VideoList :videos="queue" :columns="columnChoices" sortable paginator />
    </ElTabPane>
</template>

<script setup lang='ts'>
import { ElTabPane, vLoading } from 'element-plus';
import { onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import { QueueRefreshStatus } from './utils';

import BaseTextButton from '@/components/common/BaseTextButton.vue';
import { BaseIconRefresh, BaseIconTick } from '@/components/common/icon';
import VideoList from '@/components/VideoList/App.vue';
import { fetchNewestQueue } from '@/services/videoService';
import type { ColumnChoice } from '@/utils/ms_const';
import type { VideoAbstract } from '@/utils/videoabstract';

defineProps({
    isActive: { type: Boolean },
});

const { t } = useI18n();

const queue = ref<VideoAbstract[]>([]);
const columnChoices = ['state', 'upload_time', 'player', 'software', 'mode', 'level', 'time', 'bv', 'bvs', 'ioe', 'thrp'] as ColumnChoice[];

const loadingStatus = ref(QueueRefreshStatus.Refreshing);

onMounted(refresh);

async function refresh() {
    loadingStatus.value = QueueRefreshStatus.Refreshing;
    setTimeout(() => {
        loadingStatus.value = QueueRefreshStatus.Available;
    }, 5000);
    await fetchNewestQueue().then((data) => {
        queue.value = data;
    });
    if (loadingStatus.value == QueueRefreshStatus.Refreshing) {
        loadingStatus.value = QueueRefreshStatus.CoolingDown;
    }
}
</script>
