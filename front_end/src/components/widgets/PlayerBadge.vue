<template>
    <UserAvatar v-if="showAvatar" :user-id="userId" style="height: 1em; margin-right: 0.25em" />
    <span v-if="primaryName === ''">
        {{ t('anonymous') }}
    </span>
    <span v-else class="player-badge-name">
        <template v-if="secondaryName">
            <span class="player-badge-pair"><span class="player-badge-chunk">{{ primaryName }}</span> <span class="player-badge-chunk">({{ secondaryName }})</span></span>
        </template>
        <template v-else>{{ primaryName }}</template>
    </span>
</template>

<script setup lang="ts">
import { computed, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import UserAvatar from '@/components/widgets/UserAvatar.vue';
import { local } from '@/store/local';
import { formatName } from '@/utils/strings';
import type { UserProfile } from '@/utils/userprofile';

const props = defineProps({
    userId: { type: Number, required: true },
    user: { type: Object as PropType<UserProfile>, required: true },
    loading: { type: Boolean, default: false },
    showAvatar: { type: Boolean, default: true },
});

const i18nMessages = {
    'zh-cn': { anonymous: '匿名', local: { user: '用户' } },
    en: { anonymous: 'Anonymous', local: { user: 'User' } },
};
const { t } = useI18n({ messages: i18nMessages });

const internationalName = computed(() => {
    const { firstname, lastname } = props.user;
    return firstname && lastname ? formatName(firstname, lastname, local.value.nameFormat) : firstname || lastname;
});
function nameFor(source: typeof local.value.playerName1): string {
    return source === 'international' ? internationalName.value : props.user[source];
}
const primaryName = computed(() => {
    if (props.userId === 0) return '';
    if (props.user.isNameHidden) return props.user.username || `${t('local.user')}#${props.userId}`;
    if (props.loading || props.user.id !== props.userId) return `${t('local.user')}#${props.userId}`;
    return nameFor(local.value.playerName1) || props.user.username || `${t('local.user')}#${props.userId}`;
});
const secondaryName = computed(() => {
    if (props.userId === 0 || props.user.isNameHidden || props.loading || props.user.id !== props.userId) return '';
    if (local.value.playerNameFormat !== 'name1 (name2)') return '';
    return nameFor(local.value.playerName2);
});
const nameTitle = computed(() => (props.user.isNameHidden
    ? `${props.user.username || t('local.user')}#${props.userId}`
    : [
        `${props.user.username || '--'}#${props.userId}`,
        `${props.user.realname || '--'} (${internationalName.value || '--'})`,
    ].join('\n')));
defineExpose({ nameTitle });
</script>

<style scoped lang="less">
/* 名字默认不换行；仅 name1 (name2) 格式下两个名字之间允许断行。 */
.player-badge-name {
    white-space: nowrap;
}

.player-badge-pair {
    white-space: normal;
}

.player-badge-chunk {
    white-space: nowrap;
}
</style>
