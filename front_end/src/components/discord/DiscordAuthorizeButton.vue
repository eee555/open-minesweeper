<template>
    <BaseButton v-if="enabled" type="primary" :loading="loading" @click="authorize">
        <template #icon>
            <i class="pi pi-discord" aria-hidden="true" />
        </template>
        {{ label || t(`discord.${mode}`) }}
    </BaseButton>
    <p v-if="error" class="text-danger" role="alert">
        {{ t(`discord.errors.${error}`) }}
    </p>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { onMounted, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import { discordMessages } from './messages';

import BaseButton from '@/components/common/BaseButton.vue';
import { authorizeDiscord, discordAvailable, discordHttpError } from '@/services/discordService';

const props = defineProps({
    mode: { type: String as PropType<'link' | 'login'>, required: true },
    setExpiry: { type: Number, default: 0 },
    label: { type: String, default: '' },
});
const emit = defineEmits<{ available: [enabled: boolean] }>();
const enabled = ref(false);
const loading = ref(false);
const error = ref('');

onMounted(async () => {
    try {
        enabled.value = await discordAvailable();
        emit('available', enabled.value);
    } catch {
        // Keep the existing login and binding controls usable during an outage.
        emit('available', false);
    }
});

async function authorize() {
    if (loading.value) return;
    loading.value = true;
    error.value = '';
    try {
        await authorizeDiscord(props.mode, props.setExpiry);
    } catch (reason) {
        error.value = discordHttpError(reason);
        loading.value = false;
    }
}

const { t } = useI18n({ messages: discordMessages });
</script>
