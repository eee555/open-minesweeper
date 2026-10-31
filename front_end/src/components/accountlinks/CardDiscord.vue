<template>
    <BaseCardNormal v-show="info || enabled" class="discord-card" :style="{ borderTopColor: info?.accentColor }">
        <img v-if="info?.bannerUrl" class="discord-banner" :src="info.bannerUrl" alt="" loading="lazy" referrerpolicy="no-referrer">
        <div class="discord-identity">
            <img v-if="info?.avatarUrl" class="discord-avatar" :src="info.avatarUrl" alt="" loading="lazy" referrerpolicy="no-referrer">
            <h3 class="text-medium text-regular">
                Discord<span v-if="info"> #{{ info.id }}</span>
            </h3>
        </div>
        <p v-if="info" class="text-secondary text-small">
            {{ t('discord.privateNotice') }}
        </p>
        <dl v-if="info">
            <dt>{{ t('discord.username') }}</dt><dd>{{ info.username }}</dd>
            <dt>{{ t('discord.displayName') }}</dt><dd>{{ info.global_name || info.username }}</dd>
            <dt v-if="info.badgeNames.length">
                {{ t('discord.badgesTitle') }}
            </dt>
            <dd v-if="info.badgeNames.length" class="discord-badges">
                <span v-for="badge in info.badgeNames" :key="badge">{{ t(`discord.badges.${badge}`) }}</span>
            </dd>
            <dt>{{ t('discord.updated') }}</dt><dd>{{ toISODateTimeString(info.update_time) }}</dd>
        </dl>
        <template v-if="editable">
            <p v-if="!info" class="text-secondary">
                {{ t('discord.linkHelp') }}
            </p>
            <div class="discord-actions">
                <DiscordAuthorizeButton mode="link" :label="info ? t('discord.refresh') : undefined" @available="enabled = $event" />
                <BaseButton v-if="info" type="danger" :loading="unlinking" @click="unlink">
                    {{ t('discord.unlink') }}
                </BaseButton>
            </div>
        </template>
    </BaseCardNormal>
</template>

<script setup lang="ts">
import { ElMessageBox } from 'element-plus';
import type { PropType } from 'vue';
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseCardNormal from '@/components/common/BaseCardNormal.vue';
import DiscordAuthorizeButton from '@/components/discord/DiscordAuthorizeButton.vue';
import { discordMessages } from '@/components/discord/messages';
import { httpErrorNotification } from '@/components/Notifications';
import { unlinkDiscord } from '@/services/discordService';
import type { AccountDiscord } from '@/utils/accountlinks';
import { toISODateTimeString } from '@/utils/datetime';

defineProps({
    info: { type: Object as PropType<AccountDiscord>, default: undefined },
    editable: { type: Boolean, default: false },
});
const emit = defineEmits<{ refresh: [] }>();
const enabled = ref(false);
const unlinking = ref(false);

async function unlink() {
    if (unlinking.value) return;
    unlinking.value = true;
    try {
        const confirmed = await ElMessageBox.confirm(t('discord.unlinkConfirm'), t('discord.unlink'), {
            confirmButtonText: t('button.confirm'), cancelButtonText: t('button.cancel'), type: 'warning',
        }).then(() => true, () => false);
        if (!confirmed) return;
        await unlinkDiscord();
        emit('refresh');
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        unlinking.value = false;
    }
}

const { t } = useI18n({ messages: discordMessages });
</script>

<style scoped>
.discord-card h3 {
    margin: 0 0 0.5rem;
    overflow-wrap: anywhere;
}

.discord-identity {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.discord-avatar {
    width: 3rem;
    height: 3rem;
    object-fit: cover;
}

.discord-banner {
    display: block;
    width: 100%;
    height: 6rem;
    object-fit: cover;
    margin-bottom: 0.5rem;
}

.discord-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 0.5rem;
}

.discord-card dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.25rem 0.5rem;
}

.discord-card dd {
    margin: 0;
    overflow-wrap: anywhere;
}

.discord-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: start;
}
</style>
