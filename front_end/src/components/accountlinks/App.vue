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
        <CardAdd v-if="showManualAdd" :accountlinks="accountlinks" @add-link="addLink" />
        <CardAddMineracer v-if="showMineracerAdd" @refresh="refresh" />
    </div>
</template>

<script setup lang="ts">
import { vLoading } from 'element-plus';
import type { Component } from 'vue';
import { computed, ref, watch } from 'vue';

import CardAdd from './CardAdd.vue';
import CardAddMineracer from './CardAddMineracer.vue';
import CardBilibili from './CardBilibili.vue';
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
const isOwnAccountLinkPage = computed(() => store.player.id == store.user.id);
const showManualAdd = computed(() => isOwnAccountLinkPage.value && manualAccountLinkPlatforms.some((platform) => !accountlinks.value.has(platform)));
const showMineracerAdd = computed(() => isOwnAccountLinkPage.value && accountlinks.value.m === undefined);
const accountCardConfigs: { platform: AccountLinkPlatformType; component: Component }[] = [
    { platform: AccountLinkPlatform.Saolei, component: CardSaolei },
    { platform: AccountLinkPlatform.MSGames, component: CardMsgames },
    { platform: AccountLinkPlatform.WoM, component: CardWoM },
    { platform: AccountLinkPlatform.Bilibili, component: CardBilibili },
];

watch(() => props.userId, refresh, { immediate: true });

async function refresh() {
    if (props.userId == 0) return;
    loading.value = true;
    try {
        accountlinks.value = await fetchAccountLinks(props.userId);
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        loading.value = false;
    }
}

async function addLink(platform: AccountLinkPlatformType, identifier: string) {
    try {
        const accountlink = await addAccountLink(platform, identifier);
        accountlinks.value.addSummary(accountlink);
    } catch (error) {
        httpErrorNotification(error);
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
