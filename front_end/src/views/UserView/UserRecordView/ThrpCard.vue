<template>
    <section class="thrp-record" :aria-busy="loading">
        <h3 class="text text-large">
            {{ t('prop.thrp') }}
        </h3>
        <p v-if="failed" role="alert" class="text-danger">
            {{ t('local.loadFailed') }}
            <BaseTextButton @click="retry++">
                <i class="pi pi-refresh" aria-hidden="true" />{{ t('action.refresh') }}
            </BaseTextButton>
        </p>
        <BaseTable v-loading="loading" table-class="thrp-record-table">
            <template #head>
                <tr>
                    <th v-for="stat in thrpStats" :key="stat" scope="col" class="table-col-center">
                        {{ stat === 'e_nf' ? `${t('level.e')} NF` : t(`level.${stat}`) }}
                    </th>
                </tr>
            </template>
            <tr>
                <td v-for="stat in thrpStats" :key="stat" class="table-col-center" :data-field="stat" :style="cellStyle(stat)">
                    <ThrpRecordValue :record="record" :stat="stat" :rank="record?.ranks[stat] ?? null" />
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
import ThrpRecordValue from '@/components/visualization/ThrpRecordValue.vue';
import { fetchProfileThrpRecord, profileDataRevision } from '@/services/profileDataService';
import { thrpStats, thrpValue } from '@/services/thrpRankingService';
import type { ThrpPlayerRecord, ThrpStat } from '@/services/thrpRankingService';
import { colorThemes } from '@/store/color';
import { local } from '@/store/local';
import { getPiecewiseColorSchemeName } from '@/utils/ms_const';
import '@/styles/text.css';

const props = defineProps({ userId: { type: Number, required: true } });
const record = ref<ThrpPlayerRecord>();
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
        const result = await fetchProfileThrpRecord(userId);
        if (current) record.value = result;
    } catch {
        if (current) failed.value = true;
    } finally {
        if (current) loading.value = false;
    }
}, { immediate: true });

function cellStyle(stat: ThrpStat) {
    if (!local.value.colored || !record.value) return undefined;
    const value = thrpValue(record.value, stat);
    if (value === null) return undefined;
    return colorThemes[getPiecewiseColorSchemeName('thrp')].value.getStyle(stat === 'sum' ? value / 3 : value);
}

const i18nMessages = {
    'zh-cn': { local: { loadFailed: 'Thrp 纪录加载失败，请重试。' } },
    en: { local: { loadFailed: 'Unable to load Thrp records. Please retry.' } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.thrp-record {
    display: grid;
    gap: 8px;
    min-width: 0;
}

.thrp-record h3,
.thrp-record p {
    margin: 0;
}

:deep(.thrp-record-table th),
:deep(.thrp-record-table td) {
    width: 20%;
    white-space: nowrap;
}
</style>
