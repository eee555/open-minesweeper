<template>
    <form class="ranking-repair" @submit.prevent="rebuild">
        <label>
            {{ t('local.ranking') }}
            <select v-model="rankingName" class="base-select" :aria-label="t('local.ranking')" :disabled="working">
                <option value="saolei">{{ t('local.standard') }}</option>
                <option value="saolei_nf">{{ t('local.nf') }}</option>
                <option value="strict_ng">{{ t('local.strictNg') }}</option>
                <option value="strict_ng_nf">{{ t('local.strictNgNF') }}</option>
                <option value="thrp">{{ t('prop.thrp') }}</option>
                <option value="nf_ioe">NF IOE</option>
            </select>
        </label>
        <label>
            {{ t('local.stat') }}
            <select v-if="rankingName === 'thrp'" v-model="thrpStat" class="base-select" :aria-label="t('local.stat')" :disabled="working">
                <option v-for="field in thrpStats" :key="field" :value="field">{{ field === 'e_nf' ? `${t('level.e')} NF` : t(`level.${field}`) }}</option>
            </select>
            <select v-else-if="rankingName === 'nf_ioe'" v-model="ioeStat" class="base-select" :aria-label="t('local.stat')" :disabled="working">
                <option v-for="field in nfIOEStats" :key="field" :value="field">{{ t(`level.${field}`) }}</option>
            </select>
            <select v-else v-model="stat" class="base-select" :aria-label="t('local.stat')" :disabled="working">
                <option v-for="field in fields" :key="field" :value="field">{{ t(`local.${field}`) }}</option>
            </select>
        </label>
        <label>
            {{ t('prop.userId') }}
            <ElInputNumber v-model="userId" :aria-label="t('prop.userId')" :min="1" :precision="0" :controls="false" :disabled="working" />
        </label>
        <BaseButton native-type="submit" :disabled="!canRebuild" :loading="working">
            <template #icon>
                <i class="pi pi-refresh" aria-hidden="true" />
            </template>
            {{ t('local.rebuild') }}
        </BaseButton>
    </form>
    <output v-if="result" class="text" aria-live="polite">
        {{ t('local.completed', { stat: selectedLabel, value: result.value }) }}
        <span v-if="result.videoId">{{ t('local.videoId', { id: result.videoId }) }}</span>
    </output>
</template>

<script setup lang="ts">
import { ElInputNumber } from 'element-plus';
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { actionSuccessNotification, httpErrorNotification } from '@/components/Notifications';
import { formatNFIOEValue, nfIOEStats, nfIOEVideoId, rebuildNFIOERecord } from '@/services/nfIOERankingService';
import type { NFIOEStat } from '@/services/nfIOERankingService';
import type { SaoleiField, SaoleiRankingName } from '@/services/saoleiRankingService';
import { formatSaoleiValue, rebuildSaoleiRecord, saoleiFields, saoleiVideoId } from '@/services/saoleiRankingService';
import type { StrictNgRankingName } from '@/services/strictNgRankingService';
import { formatStrictNgValue, rebuildStrictNgRecord, strictNgFields, strictNgVideoId } from '@/services/strictNgRankingService';
import { formatThrpValue, rebuildThrpRecord, thrpStats, thrpVideoId } from '@/services/thrpRankingService';
import type { ThrpStat } from '@/services/thrpRankingService';

const rankingName = ref<SaoleiRankingName | StrictNgRankingName | 'thrp' | 'nf_ioe'>('saolei');
const stat = ref<SaoleiField>('bt');
const thrpStat = ref<ThrpStat>('b');
const ioeStat = ref<NFIOEStat>('b');
const userId = ref<number>();
const working = ref(false);
const result = ref<{ value: string; videoId?: number }>();
const canRebuild = computed(() => userId.value !== undefined && Number.isSafeInteger(userId.value) && userId.value > 0);
const isStrictNg = computed(() => rankingName.value === 'strict_ng' || rankingName.value === 'strict_ng_nf');
const fields = computed(() => (isStrictNg.value ? strictNgFields : saoleiFields));
const selectedLabel = computed(() => {
    if (rankingName.value === 'nf_ioe') return t(`level.${ioeStat.value}`);
    if (rankingName.value === 'thrp') return thrpStat.value === 'e_nf' ? `${t('level.e')} NF` : t(`level.${thrpStat.value}`);
    return t(`local.${stat.value}`);
});

watch([rankingName, stat, thrpStat, ioeStat, userId], () => {
    result.value = undefined;
});

async function rebuild() {
    if (!canRebuild.value || working.value || userId.value === undefined) return;
    working.value = true;
    result.value = undefined;
    try {
        if (rankingName.value === 'thrp') {
            const record = await rebuildThrpRecord(userId.value, thrpStat.value);
            result.value = { value: formatThrpValue(record, thrpStat.value), videoId: thrpVideoId(record, thrpStat.value) };
        } else if (rankingName.value === 'nf_ioe') {
            const record = await rebuildNFIOERecord(userId.value, ioeStat.value);
            result.value = { value: formatNFIOEValue(record, ioeStat.value), videoId: nfIOEVideoId(record, ioeStat.value) };
        } else if (rankingName.value === 'strict_ng' || rankingName.value === 'strict_ng_nf') {
            const record = await rebuildStrictNgRecord(userId.value, rankingName.value, stat.value);
            result.value = { value: formatStrictNgValue(record, stat.value), videoId: strictNgVideoId(record, stat.value) };
        } else {
            const record = await rebuildSaoleiRecord(userId.value, rankingName.value, stat.value);
            result.value = { value: formatSaoleiValue(record, stat.value), videoId: saoleiVideoId(record, stat.value) };
        }
        actionSuccessNotification();
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        working.value = false;
    }
}

const i18nMessages = {
    'zh-cn': { local: {
        ranking: '大榜',
        stat: '小榜',
        standard: '扫雷网规则（普通）',
        nf: '扫雷网规则（NF）',
        strictNg: '强无猜（普通）',
        strictNgNF: '强无猜（NF）',
        rebuild: '重建纪录',
        completed: '重建完成：{stat} {value}',
        videoId: '，录像 ID {id}',
        bt: '初级 Time',
        bb: '初级 3BV/s',
        it: '中级 Time',
        ib: '中级 3BV/s',
        et: '高级 Time',
        eb: '高级 3BV/s',
        sumt: 'Time 总和',
        sumb: '3BV/s 总和',
    } },
    en: { local: {
        ranking: 'Ranking',
        stat: 'Statistic',
        standard: 'Saolei.wang rules (Standard)',
        nf: 'Saolei.wang rules (NF)',
        strictNg: 'Strict NG (Standard)',
        strictNgNF: 'Strict NG (NF)',
        rebuild: 'Rebuild record',
        completed: 'Rebuild complete: {stat} {value}',
        videoId: ', video ID {id}',
        bt: 'Beginner Time',
        bb: 'Beginner 3BV/s',
        it: 'Intermediate Time',
        ib: 'Intermediate 3BV/s',
        et: 'Expert Time',
        eb: 'Expert 3BV/s',
        sumt: 'Time Sum',
        sumb: '3BV/s Sum',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.ranking-repair {
    display: flex;
    align-items: end;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 8px;
}

label {
    display: grid;
    gap: 4px;
    width: 220px;
    max-width: 100%;
}
</style>
