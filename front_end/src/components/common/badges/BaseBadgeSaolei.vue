<template>
    <img src="http://saolei.wang/favicon.ico" style="height: 16px; vertical-align: middle">
    <span class="text-regular text-small">
        {{ t('website.saolei') }}
    </span>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
</script>
