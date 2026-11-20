<template>
    <ElForm label-width="120px">
        <ElFormItem :label="t('local.kind')">
            <select v-model="kind" class="base-select" :aria-label="t('local.kind')" data-cy="weekly-kind">
                <option value="weekly">
                    {{ t('local.speed') }}
                </option>
                <option value="weekly-eff">
                    {{ t('local.efficiency') }}
                </option>
            </select>
        </ElFormItem>
        <ElFormItem v-if="kind === 'weekly'" :label="t('local.format')">
            <select v-model="tournamentFormat" class="base-select" style="width: 220px" :aria-label="t('local.format')">
                <option v-for="option in tournamentFormatOptions" :key="option.value" :value="option.value">
                    {{ t(option.label) }}
                </option>
            </select>
        </ElFormItem>
        <ElFormItem>
            <BaseButton type="primary" :loading="creating" @click="createWeeklyTournament">
                {{ t('local.create') }}
            </BaseButton>
        </ElFormItem>
    </ElForm>
    <ElDescriptions v-if="createdWeekly" :title="t('local.result')" border :column="2">
        <ElDescriptionsItem :label="t('prop.tournamentId')">
            {{ createdWeekly.data.id }}
        </ElDescriptionsItem>
        <ElDescriptionsItem :label="t('local.weekly')">
            {{ createdWeekly.data.year }}W{{ createdWeekly.data.week }}
        </ElDescriptionsItem>
        <ElDescriptionsItem :label="t('prop.start_time')">
            {{ formatDateTime(createdWeekly.data.start_time) }}
        </ElDescriptionsItem>
        <ElDescriptionsItem :label="t('prop.end_time')">
            {{ formatDateTime(createdWeekly.data.end_time) }}
        </ElDescriptionsItem>
    </ElDescriptions>
</template>

<script setup lang="ts">
import { ElDescriptions, ElDescriptionsItem, ElForm, ElFormItem } from 'element-plus';
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { httpErrorNotification, successNotification } from '@/components/Notifications';
import useCurrentInstance from '@/utils/common/useCurrentInstance';
import { toDate, toISODateTimeString } from '@/utils/datetime';

const { proxy } = useCurrentInstance();

const tournamentFormatOptions = [
    { label: 'local.classicFormat', value: 'c' },
] as const;

const tournamentFormat = ref(tournamentFormatOptions[0].value);
const kind = ref<'weekly' | 'weekly-eff'>('weekly');
const creating = ref(false);
const createdWeekly = ref<WeeklyCreateResponse | null>(null);

interface WeeklyCreateResponse {
    data: {
        id: number;
        year: number;
        week: number;
        start_time: string;
        end_time: string;
        state: string;
        tournament_format?: string;
    };
}

async function createWeeklyTournament() {
    creating.value = true;
    await proxy.$axios.post<WeeklyCreateResponse>(`/api/tournament/${kind.value}/new`, {
        ...kind.value === 'weekly' ? { tournament_format: tournamentFormat.value } : {},
    }).then((response) => {
        createdWeekly.value = response.data;
        successNotification(response);
    }).catch(httpErrorNotification);
    creating.value = false;
}

function formatDateTime(value: string | Date | null | undefined) {
    const date = toDate(value);
    return date ? toISODateTimeString(date) : '';
}

const i18nMessages = {
    'zh-cn': { local: {
        kind: '比赛类别',
        speed: '竞速打卡赛',
        efficiency: '效率打卡赛',
        format: '比赛类型',
        classicFormat: '2高5中',
        create: '创建下周打卡赛',
        result: '创建结果',
        weekly: '打卡赛',
    } },
    en: { local: {
        kind: 'Tournament type',
        speed: 'Speed Weekly',
        efficiency: 'Efficiency Weekly',
        format: 'Tournament format',
        classicFormat: '2 Expert + 5 Intermediate',
        create: 'Create next week’s tournament',
        result: 'Creation result',
        weekly: 'Weekly tournament',
    } },
    es: { local: {
        kind: 'Tipo de torneo',
        speed: 'Velocidad Semanal',
        efficiency: 'Eficiencia Semanal',
        format: 'Formato de torneo',
        classicFormat: '2 Expertos + 5 Intermedios',
        create: 'Crear el próximo torneo de la semana',
        result: 'Resultado de creación',
        weekly: 'Torneo semanal',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
