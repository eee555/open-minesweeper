<template>
    <div class="account-platform-grid" role="group" :aria-label="t('accountlink.platform')">
        <BaseButton v-for="platform in platforms" :key="platform.id" class="account-platform-button" :aria-pressed="model === platform.id" :aria-controls="panelId" :data-platform="platform.id" @click="model = platform.id">
            <span class="account-platform-icon" :class="{ 'is-unlinked': unlinkedPlatforms.includes(platform.id) }" aria-hidden="true">
                <span v-if="platform.mask" class="account-platform-mask" :style="{ '--account-platform-mask': `url('${platform.src}')` }" />
                <img v-else :src="platform.src" alt="">
            </span>
            <span>{{ t(`platform.${platform.id}`) }}</span>
        </BaseButton>
    </div>
</template>

<script setup lang="ts">
import './grid.css';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import { platforms } from './platforms';

import BaseButton from '@/components/common/BaseButton.vue';
import type { AccountLinkPlatform } from '@/utils/accountlinks';

defineProps({
    panelId: { type: String, required: true },
    unlinkedPlatforms: { type: Array as PropType<readonly AccountLinkPlatform[]>, required: true },
});
const model = defineModel<AccountLinkPlatform>({ required: true });
const { t } = useI18n();
</script>
