<template>
    <ElSelect v-model="model" filterable allow-create default-first-option clearable value-on-clear="" :reserve-keyword="false">
        <ElOption v-for="language in mediaLanguages" :key="language.lang" :value="language.lang" :label="language.text" />
    </ElSelect>
</template>

<script setup lang="ts">
import { ElOption, ElSelect } from 'element-plus';

import { mediaLanguages } from '@/utils/media';

const model = defineModel<string>({ required: true });
</script>
