<template>
    <span>{{ t('local.edition') }}</span>
    <ElInputNumber v-model="gscID" size="small" :min="0" />
    <br>
    <GSCGeneralInfo :id="gscID" />
    <HistoryImport :order="gscID" />
</template>

<script setup lang="ts">
import { ElInputNumber } from 'element-plus';
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import GSCGeneralInfo from '@/components/GSCAdmin/GeneralInfo.vue';
import HistoryImport from '@/components/GSCAdmin/HistoryImport.vue';

const i18nMessages = {
    'zh-cn': { local: {
        edition: '比赛届数',
    } },
    en: { local: {
        edition: 'Edition',
    } },
    es: { local: {
        edition: 'Edición',
    } },
};
const { t } = useI18n({ messages: i18nMessages });

const gscID = ref(0);
</script>
