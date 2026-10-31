<template>
    <span>第</span>
    <ElInputNumber v-model="gscID" size="small" :min="0" />
    <span>届</span>
    <br>
    <GSCGeneralInfo :id="gscID" />
    <HistoryImport :order="gscID" />
</template>

<script setup lang="ts">
import { ElInputNumber } from 'element-plus';
import { ref } from 'vue';

import GSCGeneralInfo from '@/components/GSCAdmin/GeneralInfo.vue';
import HistoryImport from '@/components/GSCAdmin/HistoryImport.vue';

const gscID = ref(0);
</script>
