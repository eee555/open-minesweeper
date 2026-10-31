<template>
    <main class="discord-result text">
        <h1 class="text-large">
            {{ t(success ? `discord.${status}` : 'discord.failed') }}
        </h1>
        <p v-if="!success" role="alert">
            {{ t(`discord.errors.${error}`) }}
        </p>
        <p v-if="error === 'not_linked'">
            {{ t('discord.loginHelp') }}
        </p>
        <RouterLink v-if="success" class="link" :to="`/player/${userId}/accountlink`">
            {{ t('discord.accounts') }}
        </RouterLink>
        <RouterLink class="link" to="/">
            {{ t('discord.home') }}
        </RouterLink>
    </main>
</template>

<script setup lang="ts">
import '@/styles/link.css';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink, useRoute } from 'vue-router';

import { discordMessages } from '@/components/discord/messages';
import { normalizeDiscordError } from '@/services/discordService';

const route = useRoute();
const status = computed(() => route.query.status);
const userId = computed(() => (typeof route.query.user_id === 'string' && (/^[1-9]\d*$/).test(route.query.user_id) ? route.query.user_id : ''));
const success = computed(() => (status.value === 'linked' || status.value === 'logged_in') && userId.value !== '' && route.query.error === undefined);
const error = computed(() => normalizeDiscordError(route.query.error));
const { t } = useI18n({ messages: discordMessages });
</script>

<style scoped>
.discord-result {
    padding: 1rem;
}

.discord-result a {
    display: inline-block;
    margin: 0.5rem 1rem 0 0;
}
</style>
