<template>
    <section v-loading="loading" class="saolei-record-scroll">
        <BaseTable table-class="saolei-record-table">
            <template #head>
                <tr>
                    <th scope="col" class="table-col-center text-secondary">
                        {{ t('ranking.saolei.title') }}
                    </th>
                    <th v-for="level in levels" :key="level" scope="col" class="table-col-center text-secondary">
                        {{ t(`level.${level}`) }}
                    </th>
                </tr>
            </template>
            <template v-for="rankingName in rankingNames" :key="rankingName">
                <tr v-for="(label, stat) in SaoleiStat" :key="stat">
                    <th scope="row" class="table-col-center text-secondary">
                        {{ t(`prop.${label}`) }}{{ rankingName === 'saolei_nf' ? ' (NF)' : '' }}
                    </th>
                    <td v-for="level in levels" :key="level" class="table-col-center">
                        <VideoPreviewLink
                            v-if="saoleiVideoId(records[rankingName], `${level}${stat}`)"
                            :id="saoleiVideoId(records[rankingName], `${level}${stat}`)"
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
import { fetchProfileSaoleiRecords, profileDataRevision } from '@/services/profileDataService';
import { formatSaoleiValue, SaoleiLevels, SaoleiStat, saoleiVideoId } from '@/services/saoleiRankingService';
import type { SaoleiField, SaoleiPlayerRecord, SaoleiRankingName } from '@/services/saoleiRankingService';

const props = defineProps({
    userId: { type: Number, required: true },
});
const records = ref<Partial<Record<SaoleiRankingName, SaoleiPlayerRecord>>>({});
const loading = ref(false);
const rankingNames: SaoleiRankingName[] = ['saolei', 'saolei_nf'];
const levels = [...SaoleiLevels, 'sum'] as const;
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
        const data = await fetchProfileSaoleiRecords(userId);
        if (active) records.value = data;
    } catch {
        if (active) ElMessage.error({ message: '竞速纪录加载失败', offset: 68 });
    } finally {
        if (active) loading.value = false;
    }
}, { immediate: true });

function formatScore(record: SaoleiPlayerRecord | undefined, stat: SaoleiField): string {
    return `${formatSaoleiValue(record, stat)}(${record?.ranks[stat] ?? '--'})`;
}
</script>

<style scoped>
.saolei-record-scroll {
    overflow-x: auto;
}

:deep(.saolei-record-table) {
    color: var(--ui-text-color-regular);
    background: var(--ui-fill-color-blank);
    font-size: var(--ui-font-size-base);
}

:deep(.saolei-record-table th),
:deep(.saolei-record-table td) {
    border: 1px solid var(--ui-border-color-lighter);
    padding: 8px 12px;
}

:deep(.saolei-record-table th) {
    background: var(--ui-fill-color-light);
}

:deep(.saolei-record-table td) {
    white-space: nowrap;
}
</style>
