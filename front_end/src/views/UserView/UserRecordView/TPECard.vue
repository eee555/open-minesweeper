<template>
    <section class="tpe-record" :aria-busy="loading">
        <h3 class="text text-large">
            TPE
        </h3>
        <p v-if="failed" role="alert" class="text-danger">
            {{ t('local.loadFailed') }}
            <BaseTextButton @click="retry++">
                <i class="pi pi-refresh" aria-hidden="true" />{{ t('action.refresh') }}
            </BaseTextButton>
        </p>
        <BaseTable v-loading="loading" table-class="tpe-record-table">
            <template #head>
                <tr>
                    <th v-for="group in tpeGroups" :key="group" scope="colgroup" colspan="3" class="table-col-center tpe-group">
                        {{ t(`level.${group}`) }}
                    </th>
                </tr>
                <tr>
                    <th v-for="column in tpeColumns" :key="column.stat" scope="col" class="table-col-center" :class="{ 'tpe-group': column.metric === 'TPE' }">
                        {{ column.metric }}
                    </th>
                </tr>
            </template>
            <tr>
                <td v-for="column in tpeColumns" :key="column.stat" class="table-col-center" :class="{ 'tpe-group': column.metric === 'TPE' }" :data-field="column.stat" :title="String(tpeValue(record, column.stat) ?? '--')" :style="cellStyle(column)">
                    <VideoPreviewLink v-if="tpeVideoId(record, column.stat)" :id="tpeVideoId(record, column.stat)">
                        {{ formatTPEValue(record, column.stat) }}
                    </VideoPreviewLink><template v-else>
                        {{ formatTPEValue(record, column.stat) }}
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
import { fetchProfileTPERecord, profileDataRevision } from '@/services/profileDataService';
import { formatTPEValue, tpeColumns, tpeGroups, tpeValue, tpeVideoId } from '@/services/tpeRankingService';
import type { TPEPlayerRecord } from '@/services/tpeRankingService';
import { colorThemes } from '@/store/color';
import { local } from '@/store/local';

const props = defineProps({ userId: { type: Number, required: true } });
const record = ref<TPEPlayerRecord>();
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
        const result = await fetchProfileTPERecord(userId);
        if (current) record.value = result;
    } catch {
        if (current) failed.value = true;
    } finally {
        if (current) loading.value = false;
    }
}, { immediate: true });

function cellStyle(column: typeof tpeColumns[number]) {
    const value = tpeValue(record.value, column.stat);
    if (!local.value.colored || column.level === 'sum' || value === null) return undefined;
    return colorThemes[`${column.level}time`].value.getStyle(value);
}

const i18nMessages = {
    'zh-cn': { local: { loadFailed: 'TPE 纪录加载失败，请重试。' } },
    en: { local: { loadFailed: 'Unable to load TPE records. Please retry.' } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.tpe-record {
    display: grid;
    gap: 8px;
    min-width: 0;
}

.tpe-record h3,
.tpe-record p {
    margin: 0;
}

:deep(.tpe-record-table th),
:deep(.tpe-record-table td) {
    min-width: 6em;
    white-space: nowrap;
}

:deep(.tpe-group) {
    border-left: 2px solid var(--ui-border-color);
}
</style>
