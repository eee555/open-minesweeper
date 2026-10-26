<template>
    <a class="link text" :href="platformlist[platform].url" target="_blank" rel="noopener noreferrer" style="vertical-align: bottom;">
        {{ t(`platform.${platform}`) }}
    </a>
</template>

<script setup lang="ts">
import '@/styles/link.css';

import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import { platformlist } from '@/utils/accountlinks';
import type { AccountLinkPlatform } from '@/utils/accountlinks';

defineProps({
    platform: {
        type: String as PropType<AccountLinkPlatform>,
        required: true,
    },
});

const { t } = useI18n();
</script>
