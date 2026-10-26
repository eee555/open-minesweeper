<template>
    <BaseTooltip ref="tooltip" :append-to="appendMedalTooltip" :before-show="allowMedalTooltip" interactive :interactive-border="12" :show-delay="200" :show-animation="0" :hide-animation="0">
        <span class="player-name" :title="nameTitle" @click="interactive && $event.stopPropagation()" @pointerenter="pointerOver = true" @pointerleave="pointerOver = false">
            <RouterLink v-if="interactive" :to="playerProfileTo" class="link link--no-underline text">
                <PlayerBadge :user-id="userId" :name="nameShown" :show-avatar="local.playerNameShowAvatar" />
            </RouterLink>
            <PlayerBadge v-else :user-id="userId" :name="nameShown" :show-avatar="local.playerNameShowAvatar" />
        </span>
        <template #content>
            <div class="player-name-medals" @pointerleave="activeMedalKey = ''">
                <span v-for="grant in shownGrants" :key="grant.key" class="medal-hit" @pointerenter="activeMedalKey = grant.key">
                    <MedalArt :series="grant.series" :code="grant.code" :stage="grant.stage" :size="32" />
                </span>
                <div v-if="activeCaption" class="medal-caption">
                    <div class="medal-caption-title">
                        {{ activeCaption.title }}
                    </div>
                    <div v-if="activeCaption.flavor" class="medal-caption-flavor">
                        {{ activeCaption.flavor }}
                    </div>
                    <div v-if="activeCaption.meaning" class="medal-caption-line">
                        {{ activeCaption.meaning }}
                    </div>
                </div>
            </div>
        </template>
    </BaseTooltip>
</template>

<script setup lang="ts" name="PlayerName">
import '@/styles/link.css';
import { computed, nextTick, onUnmounted, ref, useTemplateRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink } from 'vue-router';

import BaseTooltip from '@/components/common/BaseTooltip.vue';
import PlayerBadge from '@/components/widgets/PlayerBadge.vue';
import type { MedalStateRecord } from '@/services/medalService';
import { cachedPlayerMedalState, fetchPlayerMedalState, medalCaption, medalSeriesFromCode, medalStateVersions } from '@/services/medalService';
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

// 榜上快速划过时，后打开的名字关掉先打开的，避免多块勋章提示叠在一起。
let closeOpenNameMedals: (() => void) | null = null;

function appendMedalTooltip() {
    return document.body;
}

function claimNameMedals(close: () => void) {
    if (closeOpenNameMedals && closeOpenNameMedals !== close) closeOpenNameMedals();
    closeOpenNameMedals = close;
}

function releaseNameMedals(close: () => void) {
    if (closeOpenNameMedals === close) closeOpenNameMedals = null;
}

const user = ref(new UserProfile());
const loading = ref(false);
const medalGrants = ref<MedalStateRecord[]>([]);
const medalReady = ref(false);
const medalLoading = ref(false);
const medalShown = ref(false);
const pointerOver = ref(false);
const activeMedalKey = ref('');
let medalLoadToken = 0;
let medalUserId = props.userId;
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
function resetMedalView() {
    medalLoadToken += 1;
    medalLoading.value = false;
    medalShown.value = false;
    medalReady.value = false;
    medalGrants.value = [];
    activeMedalKey.value = '';
}
function allowMedalTooltip() {
    // 没有结果就取消这次弹出；读完后若指针还在名字上，再由 showMedalsIfHovering 打开。
    if (props.userId === 0) return false;
    if (!medalReady.value && !medalLoading.value) {
        const cached = cachedPlayerMedalState(props.userId);
        if (cached !== undefined) {
            medalGrants.value = cached;
            medalReady.value = true;
        }
    }
    if (!medalReady.value) {
        if (!medalLoading.value) void loadHoveredMedalState();
        return false;
    }
    if (!shownGrants.value.length) return false;
    medalShown.value = true;
    claimNameMedals(closeOurMedals);
}
async function loadHoveredMedalState(force = false) {
    const { userId } = props;
    if (userId === 0 || (medalLoading.value && !force)) return;
    const token = ++medalLoadToken;
    medalLoading.value = true;
    try {
        const grants = await fetchPlayerMedalState(userId);
        if (token !== medalLoadToken || props.userId !== userId) return;
        medalGrants.value = grants;
        medalReady.value = true;
        if (!shownGrants.value.length) {
            medalShown.value = false;
            tooltip.value?.hide();
            return;
        }
        await showMedalsIfHovering();
    } catch (error) {
        console.log(error);
        if (token === medalLoadToken && props.userId === userId) medalReady.value = true;
    } finally {
        if (token === medalLoadToken) medalLoading.value = false;
    }
}
function closeOurMedals() {
    activeMedalKey.value = '';
    tooltip.value?.hide();
    releaseNameMedals(closeOurMedals);
}
async function showMedalsIfHovering() {
    if (!pointerOver.value || !shownGrants.value.length) return;
    await nextTick();
    if (!pointerOver.value) return;
    claimNameMedals(closeOurMedals);
    tooltip.value?.show();
}
onUnmounted(closeOurMedals);
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
watch(() => props.userId, (userId) => {
    medalUserId = userId;
    resetMedalView();
    closeOurMedals();
});
// 版本变化时，没打开过提示的名字留到下次悬停；打开过或正在读的才重取。
watch(() => medalStateVersions[props.userId], () => {
    if (props.userId !== medalUserId) return;
    if (props.userId === 0 || (!medalShown.value && !medalLoading.value)) {
        medalLoadToken += 1;
        medalLoading.value = false;
        medalReady.value = false;
        medalGrants.value = [];
        return;
    }
    void loadHoveredMedalState(true);
});

const i18nMessages = {
    'zh-cn': { local: {
        user: '用户',
    } },
    en: { local: {
        user: 'User',
    } },
};

const { t, locale } = useI18n({ messages: i18nMessages });
const activeCaption = computed(() => {
    const grant = shownGrants.value.find((item) => item.key === activeMedalKey.value);
    return grant ? medalCaption(grant.series, grant.code, grant.stage, locale.value) : null;
});
</script>

<style scoped lang="less">
.player-name-medals {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    max-width: 280px;
}

.medal-hit {
    display: inline-flex;
    cursor: default;
}

.medal-caption {
    flex-basis: 100%;
}

.medal-caption-title {
    color: var(--ui-text-color-primary);
}

.medal-caption-flavor,
.medal-caption-line {
    color: var(--ui-text-color-secondary);
    font-size: var(--ui-font-size-small);
}
</style>
