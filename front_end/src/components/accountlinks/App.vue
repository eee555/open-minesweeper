<template>
    <div v-loading="loading" class="account-link-main">
        <template v-for="item in accountCardConfigs" :key="item.platform">
            <component
                :is="item.component"
                v-if="accountlinks.has(item.platform)"
                :id="accountlinks.getSummary(item.platform)!.identifier"
                :verified="accountlinks.getSummary(item.platform)!.verified"
                :info="accountlinks[item.platform]"
                @refresh="refresh"
            />
        </template>
        <CardMineracer v-if="accountlinks.m" :id="accountlinks.m.id" :info="accountlinks.m" />
        <CardDiscord v-if="accountlinks.d || isOwnAccountLinkPage" :info="accountlinks.d" :editable="isOwnAccountLinkPage" @refresh="refresh" />
        <CardAdd v-if="showManualAdd" :accountlinks="accountlinks" @add-link="addLink" />
        <CardAddMineracer v-if="showMineracerAdd" @refresh="refresh" />
    </div>
</template>

<script setup lang="ts">
import { vLoading } from 'element-plus';
import type { Component } from 'vue';
import { computed, onBeforeUnmount, ref, watch } from 'vue';

import CardAdd from './CardAdd.vue';
import CardAddMineracer from './CardAddMineracer.vue';
import CardBilibili from './CardBilibili.vue';
import CardDiscord from './CardDiscord.vue';
import CardMineracer from './CardMineracer.vue';
import CardMsgames from './CardMsgames.vue';
import CardSaolei from './CardSaolei.vue';
import CardWoM from './CardWoM.vue';

import { httpErrorNotification } from '@/components/Notifications';
import { addAccountLink, fetchAccountLinks } from '@/services/accountLinkService';
import { store } from '@/store';
import { AccountLinkPlatform, AccountLinks, manualAccountLinkPlatforms } from '@/utils/accountlinks';
import type { AccountLinkPlatform as AccountLinkPlatformType } from '@/utils/accountlinks';

const props = defineProps({
    userId: {
        type: Number,
        default: 0,
    },
});

const loading = ref(false);
const accountlinks = ref(new AccountLinks());
const isOwnAccountLinkPage = computed(() => store.user.id > 0 && props.userId === store.user.id);
const showManualAdd = computed(() => isOwnAccountLinkPage.value && manualAccountLinkPlatforms.some((platform) => !accountlinks.value.has(platform)));
const showMineracerAdd = computed(() => isOwnAccountLinkPage.value && accountlinks.value.m === undefined);
const accountCardConfigs: { platform: AccountLinkPlatformType; component: Component }[] = [
    { platform: AccountLinkPlatform.Saolei, component: CardSaolei },
    { platform: AccountLinkPlatform.MSGames, component: CardMsgames },
    { platform: AccountLinkPlatform.WoM, component: CardWoM },
    { platform: AccountLinkPlatform.Bilibili, component: CardBilibili },
];

let refreshVersion = 0;
const viewerContext = computed(() => `${store.sessionRevision}:${store.user.id}:${store.user.is_staff}`);
watch([() => props.userId, viewerContext], () => {
    accountlinks.value = new AccountLinks();
    void refresh();
}, { immediate: true });
onBeforeUnmount(() => {
    refreshVersion++;
});

async function refresh() {
    const version = ++refreshVersion;
    const viewer = viewerContext.value;
    const target = props.userId;
    const isCurrent = () => version === refreshVersion && viewer === viewerContext.value && target === props.userId;
    if (target === 0) {
        loading.value = false;
        return;
    }
    loading.value = true;
    try {
        const result = await fetchAccountLinks(target);
        if (isCurrent()) accountlinks.value = result;
    } catch (error) {
        if (isCurrent()) httpErrorNotification(error);
    } finally {
        if (isCurrent()) loading.value = false;
    }
}

async function addLink(platform: AccountLinkPlatformType, identifier: string) {
    const viewer = viewerContext.value;
    const target = props.userId;
    try {
        const accountlink = await addAccountLink(platform, identifier);
        if (viewer === viewerContext.value && target === props.userId) accountlinks.value.addSummary(accountlink);
    } catch (error) {
        if (viewer === viewerContext.value && target === props.userId) httpErrorNotification(error);
    }
}
</script>

<style lang="less" scoped>
.account-link-main {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(19rem, auto));
    grid-gap: 1rem;
}
</style>
