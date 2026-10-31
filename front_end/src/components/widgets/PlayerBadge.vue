<template>
    <UserAvatar v-if="showAvatar" :user-id="userId" style="height: 1em; margin-right: 0.25em" />
    <span v-if="name === ''">
        {{ t('anonymous') }}
    </span>
    <span v-else>
        {{ name }}
    </span>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

import UserAvatar from '@/components/widgets/UserAvatar.vue';

defineProps({
    userId: { type: Number, required: true },
    name: { type: String, default: '' },
    showAvatar: { type: Boolean, default: true },
});

const { t } = useI18n();
</script>
