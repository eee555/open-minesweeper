<template>
    <BaseButton v-bind="$attrs" type="primary">
        {{ t('button.confirm') }}
    </BaseButton>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

import BaseButton from './BaseButton.vue';

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
</script>
