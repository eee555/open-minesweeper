<template>
    <img src="https://minesweepergame.com/favicon.ico" style="height: 16px; vertical-align: middle;">
    <span class="text-regular text-small">
        {{ t('website.msgames') }}
    </span>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
</script>
