<template>
    <section class="path-record" :aria-busy="loading">
        <h3 class="text text-large">
            Path
        </h3>
        <p v-if="failed" role="alert" class="text-danger">
            {{ t('local.loadFailed') }}
            <BaseTextButton @click="retry++">
                <i class="pi pi-refresh" aria-hidden="true" />{{ t('action.refresh') }}
            </BaseTextButton>
        </p>
        <BaseTable v-loading="loading" table-class="path-record-table">
            <template #head>
                <tr>
                    <th v-for="group in pathGroups" :key="group" scope="colgroup" colspan="3" class="path-group table-col-center">
                        {{ t(`level.${group}`) }}
                    </th>
                </tr>
                <tr>
                    <th v-for="column in pathColumns" :key="column.stat" scope="col" class="table-col-center" :class="{ 'path-group': column.metric === 'path' }">
                        {{ column.label }}
                    </th>
                </tr>
            </template>
            <tr>
                <td v-for="column in pathColumns" :key="column.stat" class="table-col-center" :class="{ 'path-group': column.metric === 'path' }" :data-field="column.stat" :title="String(pathValue(record, column.stat) ?? '--')">
                    <VideoPreviewLink v-if="pathVideoId(record, column.stat)" :id="pathVideoId(record, column.stat)">
                        {{ formatPathValue(record, column.stat) }}
                    </VideoPreviewLink><template v-else>
                        {{ formatPathValue(record, column.stat) }}
                    </template>({{ record?.ranks[column.stat] ?? '--' }})
                </td>
            </tr>
        </BaseTable>
    </section>
</template>

<script setup lang="ts">
import { vLoading } from 'element-plus';
import { onActivated, onDeactivated, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseTable from '@/components/common/BaseTable.vue';
import BaseTextButton from '@/components/common/BaseTextButton.vue';
import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import { formatPathValue, pathColumns, pathGroups, pathValue, pathVideoId } from '@/services/pathRankingService';
import type { PathPlayerRecord } from '@/services/pathRankingService';
import { fetchProfilePathRecord, profileDataRevision } from '@/services/profileDataService';

const props = defineProps({ userId: { type: Number, required: true } });
const record = ref<PathPlayerRecord>();
const loading = ref(false);
const failed = ref(false);
const retry = ref(0);
const active = ref(true);
onActivated(() => {
    active.value = true;
});
onDeactivated(() => {
    active.value = false;
});
watch([() => props.userId, () => profileDataRevision(props.userId), active, retry], async ([userId], _, onCleanup) => {
    let current = true;
    onCleanup(() => {
        current = false;
    });
    record.value = undefined;
    loading.value = false;
    failed.value = false;
    if (!active.value || userId < 1) return;
    loading.value = true;
    try {
        const result = await fetchProfilePathRecord(userId);
        if (current) record.value = result;
    } catch {
        if (current) failed.value = true;
    } finally {
        if (current) loading.value = false;
    }
}, { immediate: true });

const i18nMessages = {
    'zh-cn': { local: { loadFailed: 'Path 纪录加载失败，请重试。' } },
    en: { local: { loadFailed: 'Unable to load Path records. Please retry.' } },
    es: { local: { loadFailed: 'No se pudieron cargar los registros de Path. Inténtalo de nuevo.' } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.path-record {
    display: grid;
    gap: 8px;
    min-width: 0;
}

.path-record h3,
.path-record p {
    margin: 0;
}

:deep(.path-record-table th),
:deep(.path-record-table td) {
    min-width: 6em;
    white-space: nowrap;
}

:deep(.path-group) {
    border-left: 2px solid var(--ui-border-color);
}
</style>
