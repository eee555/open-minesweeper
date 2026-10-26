<template>
    <img :src="MetasweeperIcon" style="height: 16px; vertical-align: middle">
    <span class="text-regular text-small">
        {{ t('website.openms') }}
    </span>
</template>

<script setup lang="ts">
import '@/styles/text.css';
import { useI18n } from 'vue-i18n';

import { MetasweeperIcon } from '@/utils/assets';

const { t } = useI18n();
</script>
