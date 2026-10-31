<template>
    <BaseButton v-bind="$attrs">
        <template #icon>
            <BaseIconPrev aria-hidden="true" />
        </template>
        {{ t('button.back') }}
    </BaseButton>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

import BaseButton from './BaseButton.vue';
import { BaseIconPrev } from './icon';

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
</script>
