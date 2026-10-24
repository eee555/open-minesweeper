<template>
    <BaseTooltip ref="tooltip" :before-show="allowMedalTooltip">
        <span class="player-name" :title="nameTitle" @click="interactive && $event.stopPropagation()" @pointerenter="pointerOver = true" @pointerleave="pointerOver = false">
            <RouterLink v-if="interactive" :to="playerProfileTo" class="link link--no-underline text">
                <PlayerBadge :user-id="userId" :name="nameShown" :show-avatar="local.playerNameShowAvatar" />
            </RouterLink>
            <PlayerBadge v-else :user-id="userId" :name="nameShown" :show-avatar="local.playerNameShowAvatar" />
        </span>
        <template #content>
            <div class="player-name-medals">
                <MedalArt v-for="grant in shownGrants" :key="grant.key" :series="grant.series" :code="grant.code" :stage="grant.stage" :size="32" />
            </div>
        </template>
    </BaseTooltip>
</template>

<script setup lang="ts" name="PlayerName">
import '@/styles/link.css';
import { computed, nextTick, ref, useTemplateRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink } from 'vue-router';

import BaseTooltip from '@/components/common/BaseTooltip.vue';
import PlayerBadge from '@/components/widgets/PlayerBadge.vue';
import type { MedalStateRecord } from '@/services/medalService';
import { fetchPlayerMedalState, medalSeriesFromCode } from '@/services/medalService';
import { fetchUserInfo } from '@/services/userService';
import { local } from '@/store/local';
import { formatName } from '@/utils/strings';
import { UserProfile } from '@/utils/userprofile';
import MedalArt from '@/views/UserView/MedalArt.vue';

const props = defineProps({
    interactive: { type: Boolean, default: true },
    userId: {
        type: Number,
        default: 0,
    },
});

const user = ref(new UserProfile());
const loading = ref(false);
const medalGrants = ref<MedalStateRecord[]>([]);
const medalReady = ref(false);
const pointerOver = ref(false);
const tooltip = useTemplateRef<{ show: () => void; hide: () => void }>('tooltip');
const internationalName = computed(() => {
    const { firstname, lastname } = user.value;
    return firstname && lastname ? formatName(firstname, lastname, local.value.nameFormat) : firstname || lastname;
});
function nameFor(source: typeof local.value.playerName1): string {
    return source === 'international' ? internationalName.value : user.value[source];
}
const nameShown = computed(() => {
    if (props.userId === 0) return '';
    if (user.value.isNameHidden) return `${t('local.user')} #${props.userId}`;
    if (loading.value || user.value.id !== props.userId) return `${t('local.user')}#${props.userId}`;
    const name1 = nameFor(local.value.playerName1) || user.value.username || `${t('local.user')}#${props.userId}`;
    const name2 = nameFor(local.value.playerName2);
    return local.value.playerNameFormat === 'name1 (name2)' && name2 ? `${name1} (${name2})` : name1;
});
const nameTitle = computed(() => (user.value.isNameHidden
    ? nameShown.value
    : [
        `${user.value.username || '--'}#${props.userId}`,
        `${user.value.realname || '--'} (${internationalName.value || '--'})`,
    ].join('\n')));
const playerProfileTo = computed(() => `/player/${props.userId}`);
const shownGrants = computed(() => medalGrants.value.flatMap((grant) => {
    const series = medalSeriesFromCode(grant.code);
    if (!series || grant.stage <= 0) return [];
    // 悬停只画勋章。timestamp 为空时不格式化时间。
    return [{ key: `${grant.code}:${grant.scope}`, series, code: grant.code, stage: grant.stage }];
}));
function allowMedalTooltip() {
    // 加载中先挡住空壳；有结果后若指针还在名字上再主动 show。
    if (!medalReady.value || !shownGrants.value.length) return false;
}
async function showMedalsIfHovering() {
    if (!pointerOver.value || !shownGrants.value.length) return;
    await nextTick();
    tooltip.value?.show();
}
watch(() => props.userId, async (newVal, _, onCleanup) => {
    let active = true;
    onCleanup(() => {
        active = false;
    });
    user.value = new UserProfile();
    loading.value = newVal !== 0;
    if (newVal === 0) return;
    try {
        const result = await fetchUserInfo(newVal);
        if (active) user.value = result;
    } catch (error) {
        console.log(error);
    } finally {
        if (active) loading.value = false;
    }
}, { immediate: true });
watch(() => props.userId, async (newVal, _, onCleanup) => {
    let active = true;
    onCleanup(() => {
        active = false;
    });
    medalReady.value = false;
    medalGrants.value = [];
    tooltip.value?.hide();
    if (newVal === 0) {
        medalReady.value = true;
        return;
    }
    try {
        const grants = await fetchPlayerMedalState(newVal);
        if (!active) return;
        medalGrants.value = grants;
        medalReady.value = true;
        await showMedalsIfHovering();
    } catch (error) {
        console.log(error);
        if (active) medalReady.value = true;
    }
}, { immediate: true });

const i18nMessages = {
    'zh-cn': { local: {
        user: '用户',
    } },
    en: { local: {
        user: 'User',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped lang="less">
.player-name-medals {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    max-width: 212px;
}
</style>
