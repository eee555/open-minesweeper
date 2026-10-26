<template>
    <form class="ranking-repair" @submit.prevent="rebuild">
        <label>
            {{ t('local.ranking') }}
            <ElSelect v-model="rankingName" :aria-label="t('local.ranking')" :disabled="working">
                <ElOption :label="t('local.standard')" value="saolei" />
                <ElOption :label="t('local.nf')" value="saolei_nf" />
                <ElOption :label="t('prop.thrp')" value="thrp" />
            </ElSelect>
        </label>
        <label>
            {{ t('local.stat') }}
            <ElSelect v-if="rankingName === 'thrp'" v-model="thrpStat" :aria-label="t('local.stat')" :disabled="working">
                <ElOption v-for="field in thrpStats" :key="field" :label="t(`level.${field}`)" :value="field" />
            </ElSelect>
            <ElSelect v-else v-model="stat" :aria-label="t('local.stat')" :disabled="working">
                <ElOption v-for="field in saoleiFields" :key="field" :label="t(`local.${field}`)" :value="field" />
            </ElSelect>
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
import { ElInputNumber, ElOption, ElSelect } from 'element-plus';
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { actionSuccessNotification, httpErrorNotification } from '@/components/Notifications';
import type { SaoleiField, SaoleiRankingName } from '@/services/saoleiRankingService';
import { formatSaoleiValue, rebuildSaoleiRecord, saoleiFields, saoleiVideoId } from '@/services/saoleiRankingService';
import { rebuildThrpRecord, thrpStats, thrpValue, thrpVideoId } from '@/services/thrpRankingService';
import type { ThrpStat } from '@/services/thrpRankingService';
import '@/styles/text.css';

const rankingName = ref<SaoleiRankingName | 'thrp'>('saolei');
const stat = ref<SaoleiField>('bt');
const thrpStat = ref<ThrpStat>('b');
const userId = ref<number>();
const working = ref(false);
const result = ref<{ value: string; videoId?: number }>();
const canRebuild = computed(() => userId.value !== undefined && Number.isSafeInteger(userId.value) && userId.value > 0);
const selectedLabel = computed(() => (rankingName.value === 'thrp' ? t(`level.${thrpStat.value}`) : t(`local.${stat.value}`)));

watch([rankingName, stat, thrpStat, userId], () => {
    result.value = undefined;
});

async function rebuild() {
    if (!canRebuild.value || working.value || userId.value === undefined) return;
    working.value = true;
    result.value = undefined;
    try {
        if (rankingName.value === 'thrp') {
            const record = await rebuildThrpRecord(userId.value, thrpStat.value);
            result.value = { value: thrpValue(record, thrpStat.value)?.toFixed(3) ?? '--', videoId: thrpVideoId(record, thrpStat.value) };
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
