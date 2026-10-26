<template>
    <span v-if="state === MS_State.Local" class="text text-info" :title="t('state.l')" :aria-label="t('state.l')" data-cy="local-video-state">
        <i class="pi pi-desktop" aria-hidden="true" />
    </span>
    <span v-else-if="state == MS_State.Identifier" :title="t('state.d')">
        <ElIcon>
            <BaseIconIdentifier style="color: var(--ui-color-warning)" />
        </ElIcon>
    </span>
    <span v-else-if="state == MS_State.Official" class="text text-success">
        <ElIcon>
            <BaseIconVerified />
        </ElIcon>
    </span>
    <span v-else-if="state == MS_State.Plain" class="text text-info">
        <ElIcon>
            <BaseIconPending />
        </ElIcon>
    </span>
    <span v-else-if="state == MS_State.Frozen" class="text text-danger">
        <ElIcon>
            <BaseIconFrozen />
        </ElIcon>
    </span>
</template>

<script setup lang="ts">
import '@/styles/text.css';
import 'primeicons/primeicons.css';
import { ElIcon } from 'element-plus';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseIconIdentifier from '@/components/common/BaseIconIdentifier.vue';
import BaseIconVerified from '@/components/common/BaseIconVerified.vue';
import { BaseIconFrozen, BaseIconPending } from '@/components/common/icon';
import { MS_State } from '@/utils/ms_const';

defineProps({
    state: {
        type: String as PropType<MS_State>,
        required: true,
    },
});

const { t } = useI18n();
</script>
