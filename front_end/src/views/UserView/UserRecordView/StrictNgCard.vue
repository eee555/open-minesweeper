<template>
    <section v-loading="loading" class="strict-ng-record-scroll">
        <BaseTable table-class="strict-ng-record-table">
            <template #head>
                <tr>
                    <th scope="col" class="table-col-center text-secondary">
                        {{ t('ranking.strict_ng.title') }}
                    </th>
                    <th v-for="level in levels" :key="level" scope="col" class="table-col-center text-secondary">
                        {{ t(`level.${level}`) }}
                    </th>
                </tr>
            </template>
            <template v-for="rankingName in rankingNames" :key="rankingName">
                <tr v-for="(label, stat) in StrictNgStat" :key="stat">
                    <th scope="row" class="table-col-center text-secondary">
                        {{ t(`prop.${label}`) }}{{ rankingName === 'strict_ng_nf' ? ' (NF)' : '' }}
                    </th>
                    <td v-for="level in levels" :key="level" class="table-col-center">
                        <VideoPreviewLink
                            v-if="strictNgVideoId(records[rankingName], `${level}${stat}`)"
                            :id="strictNgVideoId(records[rankingName], `${level}${stat}`)"
                        >
                            {{ formatScore(records[rankingName], `${level}${stat}`) }}
                        </VideoPreviewLink>
                        <span v-else>{{ formatScore(records[rankingName], `${level}${stat}`) }}</span>
                    </td>
                </tr>
            </template>
        </BaseTable>
    </section>
</template>

<script setup lang="ts">
import { ElMessage, vLoading } from 'element-plus';
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseTable from '@/components/common/BaseTable.vue';
import VideoPreviewLink from '@/components/VideoPreviewLink.vue';
import { fetchProfileStrictNgRecords, profileDataRevision } from '@/services/profileDataService';
import { formatStrictNgValue, StrictNgLevels, StrictNgStat, strictNgVideoId } from '@/services/strictNgRankingService';
import type { StrictNgField, StrictNgPlayerRecord, StrictNgRankingName } from '@/services/strictNgRankingService';

const props = defineProps({
    userId: { type: Number, required: true },
});
const records = ref<Partial<Record<StrictNgRankingName, StrictNgPlayerRecord>>>({});
const loading = ref(false);
const rankingNames: StrictNgRankingName[] = ['strict_ng', 'strict_ng_nf'];
const levels = [...StrictNgLevels, 'sum'] as const;
const { t } = useI18n();

watch([() => props.userId, () => profileDataRevision(props.userId)], async ([userId], _, onCleanup) => {
    let active = true;
    onCleanup(() => {
        active = false;
    });
    records.value = {};
    loading.value = false;
    if (!userId) return;
    loading.value = true;
    try {
        const data = await fetchProfileStrictNgRecords(userId);
        if (active) records.value = data;
    } catch {
        if (active) ElMessage.error({ message: '强无猜竞速纪录加载失败', offset: 68 });
    } finally {
        if (active) loading.value = false;
    }
}, { immediate: true });

function formatScore(record: StrictNgPlayerRecord | undefined, stat: StrictNgField): string {
    return `${formatStrictNgValue(record, stat)}(${record?.ranks[stat] ?? '--'})`;
}
</script>

<style scoped>
.strict-ng-record-scroll {
    overflow-x: auto;
}

:deep(.strict-ng-record-table) {
    color: var(--ui-text-color-regular);
    background: var(--ui-fill-color-blank);
    font-size: var(--ui-font-size-base);
}

:deep(.strict-ng-record-table th),
:deep(.strict-ng-record-table td) {
    border: 1px solid var(--ui-border-color-lighter);
    padding: 8px 12px;
}

:deep(.strict-ng-record-table th) {
    background: var(--ui-fill-color-light);
}

:deep(.strict-ng-record-table td) {
    white-space: nowrap;
}
</style>
