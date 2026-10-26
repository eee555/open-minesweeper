<template>
    <div ref="shell" class="site-shell" :class="{ 'site-shell--sidebar': sidebar && !compact }" :data-navigation-layout="sidebar ? 'sidebar' : 'top'">
        <header class="site-header" data-cy="app-header">
            <div class="site-toolbar">
                <button
                    v-if="compact" ref="brandButton" type="button" class="site-brand"
                    :aria-label="t('local.openNavigation')" :aria-expanded="drawerOpen" :aria-controls="drawerId"
                    data-cy="navigation-toggle" @click="drawerOpen = true"
                >
                    <NavigationLogo />
                </button>
                <RouterLink v-else v-slot="{ href, navigate }" to="/" custom>
                    <a ref="brandLink" :href="href" class="site-brand" :aria-label="t('local.home')" data-cy="navigation-home" @click="navigate">
                        <NavigationLogo />
                    </a>
                </RouterLink>
                <Login v-slot="controls">
                    <NavigationMenu
                        ref="navigation" class="site-menu" :class="{ 'site-menu--top': !sidebar }"
                        :items="navigationItems(controls)" :active="activeTool || (!sidebar ? activeSection : '')"
                        :label="t(sidebar ? 'local.accountTools' : 'local.siteNavigation')" :more-label="t('local.moreNavigation')"
                    />
                </Login>
            </div>
        </header>
        <aside v-if="sidebar && !compact" class="site-sidebar" data-cy="navigation-sidebar">
            <NavigationLinks :items="mainItems" :active="activeSection" :label="t('local.mainNavigation')" />
        </aside>
        <slot />
        <ElDrawer
            v-if="sidebar" v-model="drawerOpen" class="site-navigation-drawer" direction="ltr"
            :title="t('local.mainNavigation')" size="min(18rem, 90vw)" append-to-body destroy-on-close
            @close-auto-focus="restoreFocus"
        >
            <NavigationLinks :id="drawerId" :items="drawerItems" :active="activeSection" :label="t('local.mainNavigation')" @navigate="drawerOpen = false" />
        </ElDrawer>
        <ElDialog
            v-if="infoDialog !== undefined" model-value :title="infoDialogTitle" width="100%" align-center
            body-class="center" :show-close="false" append-to-body @closed="infoDialog = undefined"
        >
            <template #header>
                <h2 class="text-regular" style="justify-self: center;">
                    {{ infoDialogTitle }}
                </h2>
            </template>
            <Thanks v-if="infoDialog === 'team'" />
            <Downloads v-else />
        </ElDialog>
    </div>
</template>

<script setup lang="ts">
import '@/styles/navigation/layout.css';
import '@/styles/navigation/items.css';
import '@/styles/vendors/element-plus-navigation.css';
import 'primeicons/primeicons.css';

import { useColorMode, useElementSize, useTitle } from '@vueuse/core';
import { ElDialog, ElDrawer } from 'element-plus';
import { computed, defineAsyncComponent, nextTick, ref, useId, useTemplateRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink, useRoute } from 'vue-router';

import Login from '@/components/Login/App.vue';
import type { LoginControls } from '@/components/Login/types';
import NavigationLinks from '@/components/navigation/NavigationLinks.vue';
import NavigationLogo from '@/components/navigation/NavigationLogo.vue';
import NavigationMenu from '@/components/navigation/NavigationMenu.vue';
import type { NavigationItem } from '@/components/navigation/types';
import { useLanguage } from '@/components/widgets/useLanguage';
import { local, store } from '@/store';
import { LoginStatus } from '@/utils/common/structInterface';
import { getDocsUrl } from '@/utils/docs';

const Downloads = defineAsyncComponent(() => import('@/components/dialogs/Downloads.vue'));
const Thanks = defineAsyncComponent(() => import('@/components/dialogs/Thanks.vue'));

defineSlots<{ default?: () => unknown }>();
const shell = useTemplateRef<HTMLElement>('shell');
const brandButton = useTemplateRef<HTMLButtonElement>('brandButton');
const brandLink = useTemplateRef<HTMLAnchorElement>('brandLink');
const navigation = useTemplateRef<InstanceType<typeof NavigationMenu>>('navigation');
const { width } = useElementSize(shell);
const sidebar = computed(() => local.value.navigation_layout === 'sidebar');
const compact = computed(() => sidebar.value && width.value < 760);
const drawerOpen = ref(false);
const infoDialog = ref<'team' | 'downloads'>();
const infoDialogTitle = computed(() => (infoDialog.value === 'team' ? t('local.team') : t('common.software.software_download')));
const drawerId = `navigation-${useId()}`;
const route = useRoute();
const language = useLanguage();
const colorMode = useColorMode();

watch(() => local.value.navigation_layout, (value) => {
    if (value !== 'top' && value !== 'sidebar') local.value.navigation_layout = 'top';
}, { immediate: true });
watch(colorMode, (value) => {
    local.value.darkmode = value === 'dark';
}, { immediate: true });
watch([sidebar, compact], () => {
    const focused = document.activeElement;
    const needsFocus = drawerOpen.value || focused === brandButton.value
        || (focused instanceof HTMLElement && focused.closest('.site-menu, .site-sidebar') !== null);
    closeNavigation();
    if (needsFocus) restoreFocus();
});
watch(() => route.fullPath, closeNavigation);

function closeNavigation() {
    drawerOpen.value = false;
    navigation.value?.close();
}

function restoreFocus() {
    void nextTick(() => (compact.value ? brandButton.value : brandLink.value)?.focus());
}

const mainItems = computed<NavigationItem[]>(() => [
    { id: 'ranking', label: t('local.ranking'), to: '/ranking' },
    { id: 'database', label: t('local.database'), to: '/database' },
    { id: 'tournament', label: t('tournament.tournament'), to: '/tournament' },
    { id: 'minigame', label: t('common.minigame.title'), to: '/minigame/left-click' },
    { id: 'server', label: t('local.server'), to: '/server' },
].map((item) => ({ ...item, primary: true })));
const drawerItems = computed<NavigationItem[]>(() => [
    { id: 'home', label: t('local.home'), to: '/' }, ...mainItems.value,
]);
const activeSection = computed(() => {
    const section = route.path.split('/')[1] ?? '';
    return section === 'video' ? 'database' : route.path === '/' ? 'home' : section;
});
const activeTool = computed(() => {
    const profile = `/player/${store.user.id}`;
    if (route.path === profile || route.path.startsWith(`${profile}/`)) return 'profile';
    if (route.path.startsWith('/staff')) return 'staff';
    return route.path.startsWith('/settings') ? 'settings' : '';
});

function navigationItems(controls: LoginControls): NavigationItem[] {
    const items: NavigationItem[] = store.login_status === LoginStatus.IsLogin
        ? [
            { id: 'logout', label: controls.labels.logout, action: controls.logout },
            { id: 'profile', label: store.user.username, icon: 'pi-user', to: `/player/${store.user.id}` },
            ...store.user.is_staff ? [{ id: 'staff', label: t('local.staff'), icon: 'pi-shield', iconOnly: true, to: '/staff' }] : [],
        ]
        : [
            { id: 'login',
                label: controls.labels.login,
                action: () => {
                    controls.open('login');
                } },
            { id: 'register',
                label: controls.labels.register,
                action: () => {
                    controls.open('register');
                } },
        ];
    items.push(
        { id: 'settings', label: t('common.settings'), icon: 'pi-cog', iconOnly: true, to: '/settings' },
        { id: 'docs', label: t('local.docs'), icon: 'pi-question-circle', iconOnly: true, href: getDocsUrl('') },
    );
    items.push({
        id: 'language',
        label: t('local.language'),
        icon: 'pi-language',
        iconOnly: true,
        testId: 'languagePicker',
        children: language.options.map((option) => ({
            id: `language-${option.lang}`,
            label: option.text,
            checked: local.value.language === option.lang,
            action: () => {
                language.changeLanguage(option.lang);
            },
        })),
    });
    items.push({
        id: 'theme',
        label: t('local.theme'),
        icon: local.value.darkmode ? 'pi-moon' : 'pi-sun',
        iconOnly: true,
        testId: 'themePicker',
        children: (['light', 'auto', 'dark'] as const).map((mode) => ({
            id: `theme-${mode}`,
            label: t(`local.${mode}`),
            icon: mode === 'auto' ? 'pi-desktop' : mode === 'light' ? 'pi-sun' : 'pi-moon',
            checked: colorMode.store.value === mode,
            action: () => {
                colorMode.store.value = mode;
            },
        })),
    });
    items.push({
        id: 'about',
        label: t('local.about'),
        children: [
            { id: 'team',
                label: t('local.team'),
                action: () => {
                    infoDialog.value = 'team';
                } },
            { id: 'downloads',
                label: t('common.software.software_download'),
                action: () => {
                    infoDialog.value = 'downloads';
                } },
        ],
    }, {
        id: 'contact',
        label: t('local.contact'),
        children: ([
            ['github', 'GitHub', 'https://github.com/eee555/saolei_website'],
            ['gitee', 'Gitee', 'https://gitee.com/ee55/saolei_website'],
            ['discord', 'Discord', 'https://discord.gg/ks8ngPX5bT'],
            ['qq', 'QQ', 'https://qm.qq.com/q/hNShGUQkJG'],
        ] as const).map(([id, label, href]) => ({ id: `contact-${id}`, label, href, target: '_blank' as const })),
    });
    return sidebar.value ? items : [...mainItems.value, ...items];
}

const i18nMessages = {
    'zh-cn': { local: {
        siteName: '开源扫雷网',
        home: '首页',
        ranking: '排行榜',
        database: '数据库',
        staff: '管理',
        docs: '帮助',
        server: '服务器',
        language: '语言',
        theme: '颜色主题',
        about: '关于我们',
        team: '团队',
        contact: '联系我们',
        light: '浅色',
        auto: '自动',
        dark: '深色',
        accountTools: '账号与工具',
        mainNavigation: '主导航',
        siteNavigation: '站点导航',
        moreNavigation: '更多导航',
        openNavigation: '打开主导航',
    } },
    en: { local: {
        siteName: 'OpenMS',
        home: 'Home',
        ranking: 'Ranking',
        database: 'Database',
        staff: 'Moderate',
        docs: 'Help',
        server: 'Server',
        language: 'Language',
        theme: 'Color theme',
        about: 'About',
        team: 'Team',
        contact: 'Contact',
        light: 'Light',
        auto: 'Auto',
        dark: 'Dark',
        accountTools: 'Account and tools',
        mainNavigation: 'Main navigation',
        siteNavigation: 'Site navigation',
        moreNavigation: 'More navigation',
        openNavigation: 'Open navigation',
    } },
    de: { local: {
        ranking: 'Ranking',
        database: 'Datenbank',
        docs: 'Hilfe',
    } },
    pl: { local: {
        ranking: 'ranking',
        database: 'Baza danych',
        docs: 'pomoc',
    } },
};

const { t } = useI18n({ messages: i18nMessages });

const sectionTitle = computed(() => {
    const section = activeSection.value;
    const item = drawerItems.value.find(({ id }) => id === section);
    if (item) return item.label;
    if (section === 'player') return t('common.prop.player');
    if (section === 'settings') return t('common.settings');
    if (section === 'staff' || section === 'gsc') return t('local.staff');
    return '';
});
useTitle(computed(() => [t('local.siteName'), sectionTitle.value].filter(Boolean).join(' - ')));
</script>
