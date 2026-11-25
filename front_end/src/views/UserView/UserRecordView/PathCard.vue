<template>
    <section class="path-record" :aria-busy="loading">
        <p v-if="failed" role="alert" class="text-danger">
            {{ t('local.loadFailed') }}
            <BaseTextButton @click="retry++">
                <i class="pi pi-refresh" aria-hidden="true" />{{ t('action.refresh') }}
            </BaseTextButton>
        </p>
        <BaseTable v-loading="loading" table-class="path-record-table">
            <template #head>
                <tr>
                    <th scope="col" class="table-col-center">
                        {{ t('local.efficiency') }}
                    </th>
                    <th v-for="group in pathGroups" :key="group" scope="col" class="table-col-center">
                        {{ t(`level.${group}`) }}
                    </th>
                </tr>
            </template>
            <tr>
                <th scope="row" class="table-col-center">
                    {{ t('prop.thrp') }}
                </th>
                <td v-for="group in pathGroups" :key="group" class="table-col-center" :data-field="`thrp_${group}`" :style="thrpCellStyle(group)">
                    <ThrpRecordValue :record="thrpRecord" :stat="group" :rank="thrpRecord?.ranks[group] ?? null" />
                </td>
            </tr>
            <tr>
                <th scope="row" class="table-col-center">
                    NF IOE
                </th>
                <td v-for="group in pathGroups" :key="group" class="table-col-center" :data-field="`nf_ioe_${group}`" :style="nfIOECellStyle(group)">
                    <VideoPreviewLink v-if="nfIOERecord && nfIOEVideoId(nfIOERecord, group)" :id="nfIOEVideoId(nfIOERecord, group)">
                        {{ formatNFIOEScore(group) }}
                    </VideoPreviewLink><template v-else>
                        {{ formatNFIOEScore(group) }}
                    </template>({{ nfIOERecord?.ranks[group] ?? '--' }})
                </td>
            </tr>
            <tr v-for="suffix in tpeSuffixes" :key="suffix">
                <th scope="row" class="table-col-center">
                    TPE{{ suffix }}
                </th>
                <template v-for="group in pathGroups" :key="group">
                    <td v-if="group === 'b'" />
                    <td v-else class="table-col-center" :data-field="`tpe_${group}${suffix}`" :title="String(tpeValue(tpeRecord, `${group}${suffix}`) ?? '--')" :style="tpeCellStyle(`${group}${suffix}`, group)">
                        <VideoPreviewLink v-if="tpeVideoId(tpeRecord, `${group}${suffix}`)" :id="tpeVideoId(tpeRecord, `${group}${suffix}`)">
                            {{ formatTPEValue(tpeRecord, `${group}${suffix}`) }}
                        </VideoPreviewLink><template v-else>
                            {{ formatTPEValue(tpeRecord, `${group}${suffix}`) }}
                        </template>({{ tpeRecord?.ranks[`${group}${suffix}`] ?? '--' }})
                    </td>
                </template>
            </tr>
            <tr v-for="metric in pathMetrics" :key="metric">
                <th scope="row" class="table-col-center">
                    {{ pathMetricLabels[metric] }}
                </th>
                <td v-for="group in pathGroups" :key="group" class="table-col-center" :data-field="`${group}_${metric}`" :title="String(pathValue(record, `${group}_${metric}`) ?? '--')">
                    <VideoPreviewLink v-if="pathVideoId(record, `${group}_${metric}`)" :id="pathVideoId(record, `${group}_${metric}`)">
                        {{ formatPathValue(record, `${group}_${metric}`) }}
                    </VideoPreviewLink><template v-else>
                        {{ formatPathValue(record, `${group}_${metric}`) }}
                    </template>({{ record?.ranks[`${group}_${metric}`] ?? '--' }})
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
import ThrpRecordValue from '@/components/visualization/ThrpRecordValue.vue';
import { nfIOEValue, nfIOEVideoId } from '@/services/nfIOERankingService';
import type { NFIOEPlayerRecord } from '@/services/nfIOERankingService';
import { formatPathValue, pathGroups, pathMetricLabels, pathMetrics, pathValue, pathVideoId } from '@/services/pathRankingService';
import type { PathPlayerRecord } from '@/services/pathRankingService';
import { fetchProfileNFIOERecord, fetchProfilePathRecord, fetchProfileThrpRecord, fetchProfileTPERecord, profileDataRevision } from '@/services/profileDataService';
import { thrpValue } from '@/services/thrpRankingService';
import type { ThrpPlayerRecord } from '@/services/thrpRankingService';
import { formatTPEValue, tpeSuffixes, tpeValue, tpeVideoId } from '@/services/tpeRankingService';
import type { TPEPlayerRecord, TPEStat } from '@/services/tpeRankingService';
import { colorThemes } from '@/store/color';
import { local } from '@/store/local';
import { getPiecewiseColorSchemeName } from '@/utils/ms_const';

const props = defineProps({ userId: { type: Number, required: true } });
const record = ref<PathPlayerRecord>();
const thrpRecord = ref<ThrpPlayerRecord>();
const tpeRecord = ref<TPEPlayerRecord>();
const nfIOERecord = ref<NFIOEPlayerRecord>();
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
    thrpRecord.value = undefined;
    tpeRecord.value = undefined;
    nfIOERecord.value = undefined;
    loading.value = false;
    failed.value = false;
    if (!active.value || userId < 1) return;
    loading.value = true;
    const [path, thrp, tpe, nfIOE] = await Promise.allSettled([
        fetchProfilePathRecord(userId), fetchProfileThrpRecord(userId), fetchProfileTPERecord(userId), fetchProfileNFIOERecord(userId),
    ]);
    if (!current) return;
    record.value = path.status === 'fulfilled' ? path.value : undefined;
    thrpRecord.value = thrp.status === 'fulfilled' ? thrp.value : undefined;
    tpeRecord.value = tpe.status === 'fulfilled' ? tpe.value : undefined;
    nfIOERecord.value = nfIOE.status === 'fulfilled' ? nfIOE.value : undefined;
    failed.value = [path, thrp, tpe, nfIOE].some((result) => result.status === 'rejected');
    loading.value = false;
}, { immediate: true });

function thrpCellStyle(group: typeof pathGroups[number]) {
    const value = thrpRecord.value ? thrpValue(thrpRecord.value, group) : null;
    if (!local.value.colored || value === null) return undefined;
    return colorThemes[getPiecewiseColorSchemeName('thrp')].value.getStyle(group === 'sum' ? value / 3 : value);
}

function tpeCellStyle(stat: TPEStat, group: 'i' | 'e' | 'sum') {
    const value = tpeValue(tpeRecord.value, stat);
    if (!local.value.colored || group === 'sum' || value === null) return undefined;
    return colorThemes[`${group}time`].value.getStyle(value);
}

function nfIOECellStyle(group: typeof pathGroups[number]) {
    const value = nfIOERecord.value ? nfIOEValue(nfIOERecord.value, group) : null;
    if (!local.value.colored || value === null) return undefined;
    return colorThemes.ioe.value.getStyle(group === 'sum' ? value / 3 : value);
}

function formatNFIOEScore(group: typeof pathGroups[number]): string {
    const value = nfIOERecord.value ? nfIOEValue(nfIOERecord.value, group) : null;
    return value?.toFixed(3) ?? '--';
}

const i18nMessages = {
    'zh-cn': { local: { efficiency: '效率', loadFailed: '部分效率纪录加载失败，请重试。' } },
    en: { local: { efficiency: 'Efficiency', loadFailed: 'Unable to load some efficiency records. Please retry.' } },
    es: { local: { efficiency: 'Eficiencia', loadFailed: 'No se pudieron cargar algunos registros de eficiencia. Inténtalo de nuevo.' } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.path-record {
    display: grid;
    gap: 8px;
    min-width: 0;
}

.path-record p {
    margin: 0;
}

:deep(.path-record-table td) {
    white-space: nowrap;
}

:deep(.path-record-table th:first-child) {
    white-space: normal;
    word-break: normal;
    overflow-wrap: normal;
    hyphens: none;
}
</style>
