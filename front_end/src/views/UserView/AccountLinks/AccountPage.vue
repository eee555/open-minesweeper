<template>
    <div class="account-links-page" :aria-busy="loading">
        <PlatformGrid :model-value="selected" :panel-id="panelId" :unlinked-platforms="unlinkedPlatforms" @update:model-value="selectPlatform" />
        <section :id="panelId" class="account-details" :aria-labelledby="`${panelId}-title`" data-cy="account-details">
            <h2 :id="`${panelId}-title`">
                {{ t(`platform.${selected}`) }}<span v-if="identifier && !privateHidden"> #{{ identifier }}</span>
            </h2>
            <p v-if="loading && !loaded" role="status">
                {{ t('local.loading') }}
            </p>
            <div v-else-if="loadError && !loaded" role="alert">
                <p>{{ t('local.loadFailed') }}</p>
                <BaseButton @click="refresh">
                    {{ t('button.retry') }}
                </BaseButton>
            </div>
            <template v-else>
                <p v-if="loadError" class="text-danger" role="alert">
                    {{ t('local.loadFailed') }} <BaseButton text @click="refresh">
                        {{ t('button.retry') }}
                    </BaseButton>
                </p>
                <p v-if="privateHidden" class="text-secondary">
                    {{ t('local.privateNotice') }}
                </p>
                <template v-else-if="linked">
                    <SaoleiPanel v-if="selected === 'c'" :key="selected" :verified="verified" :info="links.c" @refresh="refresh" />
                    <MsgamesPanel v-else-if="selected === 'a'" :key="selected" :verified="verified" :info="links.a" />
                    <WoMPanel v-else-if="selected === 'w'" :key="selected" :verified="verified" :info="links.w" :owner="ownPage" @refresh="refresh" />
                    <BilibiliPanel v-else-if="selected === 'B'" :key="selected" :verified="verified" :info="links.B" :owner="ownPage" @refresh="refresh" />
                    <MineracerPanel v-else-if="selected === 'm'" :info="links.m" />
                    <ClassicPanel v-else-if="selected === 'x'" :info="links.x" />
                    <PrivatePanel v-else-if="selected === 'q' || selected === 'd'" :verified="verified" />
                </template>
                <template v-else-if="ownPage">
                    <MineracerLink v-if="selected === 'm'" :flow="mineracerFlow" />
                    <ClassicLink v-else-if="selected === 'x'" :flow="classicFlow" />
                    <SaoleiLink v-else-if="selected === 'c'" v-model="drafts.c" :sending="sending.c" :error="errors.c" @submit="submitLink('c')" />
                    <MsgamesLink v-else-if="selected === 'a'" v-model="drafts.a" :sending="sending.a" :error="errors.a" @submit="submitLink('a')" />
                    <WomLink v-else-if="selected === 'w'" v-model="drafts.w" :sending="sending.w" :error="errors.w" @submit="submitLink('w')" />
                    <BilibiliLink v-else-if="selected === 'B'" v-model="drafts.B" :sending="sending.B" :error="errors.B" @submit="submitLink('B')" />
                    <QQLink v-else-if="selected === 'q'" v-model="drafts.q" :sending="sending.q" :error="errors.q" @submit="submitLink('q')" />
                    <DiscordLink v-else-if="selected === 'd'" v-model="drafts.d" :sending="sending.d" :error="errors.d" @submit="submitLink('d')" />
                </template>
                <p v-else class="text-secondary">
                    {{ t('local.noPublicLink') }}
                </p>
            </template>
        </section>
    </div>
</template>

<script setup lang="ts">
import './page.css';
import { computed, onMounted, reactive, ref, useId } from 'vue';
import { useI18n } from 'vue-i18n';

import BilibiliLink from './linking/BilibiliLink.vue';
import ClassicLink from './linking/ClassicLink.vue';
import DiscordLink from './linking/DiscordLink.vue';
import MineracerLink from './linking/MineracerLink.vue';
import MsgamesLink from './linking/MsgamesLink.vue';
import QQLink from './linking/QQLink.vue';
import SaoleiLink from './linking/SaoleiLink.vue';
import { useClassicLink } from './linking/useClassicLink';
import { useMineracerLink } from './linking/useMineracerLink';
import WomLink from './linking/WomLink.vue';
import BilibiliPanel from './panels/BilibiliPanel.vue';
import ClassicPanel from './panels/ClassicPanel.vue';
import MineracerPanel from './panels/MineracerPanel.vue';
import MsgamesPanel from './panels/MsgamesPanel.vue';
import PrivatePanel from './panels/PrivatePanel.vue';
import SaoleiPanel from './panels/SaoleiPanel.vue';
import WoMPanel from './panels/WoMPanel.vue';
import PlatformGrid from './PlatformGrid.vue';
import { platforms } from './platforms';
import { useActivePanel } from './useActivePanel';

import BaseButton from '@/components/common/BaseButton.vue';
import { httpErrorNotification } from '@/components/Notifications';
import { addAccountLink, fetchAccountLinks } from '@/services/accountLinkService';
import { store } from '@/store';
import { AccountLinks } from '@/utils/accountlinks';
import type { AccountLinkPlatform } from '@/utils/accountlinks';

const props = defineProps({ userId: { type: Number, required: true } });
const panelId = `account-details-${useId()}`;
const isActive = useActivePanel();
const links = ref(new AccountLinks());
const selected = ref<AccountLinkPlatform>('c');
const loading = ref(true);
const loaded = ref(false);
const loadError = ref(false);
const drafts = reactive(Object.fromEntries(platforms.map(({ id }) => [id, ''])) as Record<AccountLinkPlatform, string>);
const errors = reactive({ ...drafts });
const sending = reactive(Object.fromEntries(platforms.map(({ id }) => [id, false])) as Record<AccountLinkPlatform, boolean>);
const ownPage = computed(() => store.user.id > 0 && store.user.id === props.userId);
const unlinkedPlatforms = computed(() => (loaded.value ? platforms.filter(({ id, private: hidden }) => (!hidden || ownPage.value || store.user.is_staff) && !hasLink(id)).map(({ id }) => id) : []));
const privateHidden = computed(() => (selected.value === 'd' || selected.value === 'q') && !ownPage.value && !store.user.is_staff);
const linked = computed(() => hasLink(selected.value));
const identifier = computed(() => {
    if (privateHidden.value) return '';
    if (selected.value === 'm') return links.value.m?.id ?? '';
    if (selected.value === 'x') return links.value.x?.id.toString() ?? '';
    return links.value.getSummary(selected.value)?.identifier ?? '';
});
const verified = computed(() => links.value.getSummary(selected.value)?.verified ?? false);
let revision = 0;
let manuallySelected = false;
const mineracerFlow = useMineracerLink(computed(() => loaded.value && ownPage.value && selected.value === 'm' && !linked.value), refresh);
const classicFlow = useClassicLink(computed(() => loaded.value && ownPage.value && selected.value === 'x' && !linked.value), refresh);

function hasLink(platform: AccountLinkPlatform) {
    if (platform === 'm') return links.value.m !== undefined;
    if (platform === 'x') return links.value.x !== undefined;
    return links.value.has(platform);
}

function selectPlatform(platform: AccountLinkPlatform) {
    selected.value = platform;
    manuallySelected = true;
}

async function refresh() {
    const current = ++revision;
    if (props.userId === 0) {
        loading.value = false; return;
    }
    loading.value = true;
    loadError.value = false;
    try {
        const result = await fetchAccountLinks(props.userId);
        if (!isActive() || current !== revision) return;
        links.value = result;
        if (!loaded.value && !manuallySelected) {
            selected.value = platforms.find(({ id, private: hidden }) => (!hidden || ownPage.value || store.user.is_staff) && hasLink(id))?.id ?? 'c';
        }
        loaded.value = true;
    } catch (error) {
        if (isActive() && current === revision) {
            loadError.value = true; httpErrorNotification(error);
        }
    } finally {
        if (isActive() && current === revision) loading.value = false;
    }
}

async function submitLink(platform: AccountLinkPlatform) {
    if (!isActive() || !ownPage.value || sending[platform] || hasLink(platform)) return;
    const submittedId = drafts[platform];
    sending[platform] = true;
    errors[platform] = '';
    try {
        const summary = await addAccountLink(platform, submittedId);
        if (!isActive()) return;
        links.value.addSummary(summary);
        drafts[platform] = '';
    } catch (error) {
        if (isActive()) {
            errors[platform] = t('local.addFailed'); httpErrorNotification(error);
        }
    } finally {
        if (isActive()) sending[platform] = false;
    }
}

onMounted(() => {
    void refresh();
});
const i18nMessages = {
    'zh-cn': { local: {
        loading: '正在加载账号关联…',
        loadFailed: '账号关联加载失败，请重试。',
        addFailed: '关联失败，请核对输入后重试。',
        noPublicLink: '暂无可展示的关联。',
        privateNotice: '私密关联，仅本人和本站管理员可见。',
    } },
    en: { local: {
        loading: 'Loading linked accounts…',
        loadFailed: 'Could not load linked accounts. Please retry.',
        addFailed: 'Could not link the account. Check the ID and retry.',
        noPublicLink: 'No account link is available to display.',
        privateNotice: 'Private links are visible only to the account owner and site moderators.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
