<template>
    <Tippy interactive animate-fill arrow trigger="click" append-to="parent">
        <BaseTextButton underline="never" :aria-label="t('common.settings')">
            <BaseIconSetting />
        </BaseTextButton>
        <template #content>
            <BaseCardNormal style="width: auto;">
                <slot />
            </BaseCardNormal>
        </template>
    </Tippy>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import { Tippy } from 'vue-tippy';

import BaseCardNormal from '../common/BaseCardNormal.vue';

import BaseTextButton from '@/components/common/BaseTextButton.vue';
import { BaseIconSetting } from '@/components/common/icon';

defineSlots<{
    default?: () => unknown;
}>();

const { t } = useI18n();
</script>
