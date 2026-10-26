<template>
    <ElForm label-width="120px">
        <ElFormItem :label="t('local.format')">
            <ElSelect v-model="tournamentFormat" style="width: 220px">
                <ElOption
                    v-for="option in tournamentFormatOptions"
                    :key="option.value"
                    :label="t(option.label)"
                    :value="option.value"
                />
            </ElSelect>
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
import { ElDescriptions, ElDescriptionsItem, ElForm, ElFormItem, ElOption, ElSelect } from 'element-plus';
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
        tournament_format: string;
    };
}

async function createWeeklyTournament() {
    creating.value = true;
    await proxy.$axios.post('/api/tournament/weekly/new', {
        tournament_format: tournamentFormat.value,
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
        format: '比赛类型',
        classicFormat: '2高5中',
        create: '创建下周打卡赛',
        result: '创建结果',
        weekly: '打卡赛',
    } },
    en: { local: {
        format: 'Tournament format',
        classicFormat: '2 Expert + 5 Intermediate',
        create: 'Create next week’s tournament',
        result: 'Creation result',
        weekly: 'Weekly tournament',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
