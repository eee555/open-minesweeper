<template>
    <div class="resources-view">
        <header class="resources-header">
            <h1 class="text-large">
                {{ t('local.title') }}
            </h1>
            <p class="text-small">
                {{ t('local.subtitle') }}
            </p>
        </header>

        <ElTabs :model-value="activeTab" class="resources-tabs" @tab-click="openTab">
            <ElTabPane v-for="item in sections" :key="item.id" :name="item.id">
                <template #label>
                    <SoftwareIcon v-if="item.software" :software="item.software" />
                    <img v-else-if="item.icon" :src="item.icon" :alt="item.label" width="16" height="16">
                    <span class="resources-tab-label">{{ t(`local.${item.id}`) }}</span>
                </template>
                <section class="resources-panel" :data-cy="`resource-${item.id}`">
                    <component :is="item.component" />
                </section>
            </ElTabPane>
        </ElTabs>
    </div>
</template>

<script setup lang="ts">
import { ElTabPane, ElTabs } from 'element-plus';
import type { TabsPaneContext } from 'element-plus';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import yuanshenToolboxIcon from '@/assets/img/yuanshen-toolbox.png';
import analyzerIcon from '@/assets/video-analyzer.svg';
import AnalyzerHelper from '@/components/dialogs/AnalyzerHelper.vue';
import ArbiterHelper from '@/components/dialogs/ArbiterHelper.vue';
import MetasweeperHelper from '@/components/dialogs/MetasweeperHelper.vue';
import ViennaSweeperHelper from '@/components/dialogs/ViennaSweeperHelper.vue';
import YuanshenToolboxHelper from '@/components/dialogs/YuanshenToolboxHelper.vue';
import SoftwareIcon from '@/components/widgets/SoftwareIcon.vue';
import type { MS_Software } from '@/utils/ms_const';

// label 只用作图片标签的替代文本，标签页显示的是 local.<id> 的本地化名称。
const sections: { id: string; label: string; software?: MS_Software; icon?: string; component: unknown }[] = [
    { id: 'metasweeper', label: 'Metasweeper', software: 'e', component: MetasweeperHelper },
    { id: 'arbiter', label: 'Minesweeper Arbiter', software: 'a', component: ArbiterHelper },
    { id: 'vienna', label: 'ViennaSweeper', software: 'r', component: ViennaSweeperHelper },
    { id: 'analyzer', label: 'OpenMinesweeper Video Analyzer', icon: analyzerIcon, component: AnalyzerHelper },
    { id: 'yuanshen', label: 'Yuanshen Toolbox', icon: yuanshenToolboxIcon, component: YuanshenToolboxHelper },
];
const defaultTab = sections[0].id;

const route = useRoute();
const router = useRouter();
// 路由承载当前标签，刷新与分享链接都能回到同一项资源。
const activeTab = computed(() => {
    const current = route.path.split('/')[2] ?? '';
    return sections.some((item) => item.id === current) ? current : defaultTab;
});

function openTab(tab: TabsPaneContext) {
    const name = String(tab.paneName ?? '');
    if (name === activeTab.value || !sections.some((item) => item.id === name)) return;
    void router.push(`/resources/${name}`);
}

const i18nMessages = {
    'zh-cn': { local: {
        title: '资源',
        subtitle: '本页汇总本站推荐与维护的扫雷软件和工具。下载后请核对版本与发布说明。',
        metasweeper: '元扫雷',
        arbiter: '阿比特',
        vienna: '维也纳扫雷',
        analyzer: '录像分析器',
        yuanshen: '元神工具箱',
    } },
    en: { local: {
        title: 'Resources',
        subtitle: 'Software and tools recommended and maintained by this site. Check the version and release notes after downloading.',
        metasweeper: 'Metasweeper',
        arbiter: 'Arbiter',
        vienna: 'ViennaSweeper',
        analyzer: 'Video Analyzer',
        yuanshen: 'Yuanshen Toolbox',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.resources-view {
    box-sizing: border-box;
    container-type: inline-size;
    display: grid;
    gap: 10px;
    min-width: 0;
    padding: 1%;
}

.resources-header {
    display: grid;
    gap: 4px;
}

.resources-header h1,
.resources-header p {
    margin: 0;
}

.resources-tab-label {
    margin-left: 4px;
}

.resources-panel {
    min-width: 0;
}

.resources-panel :deep(h3) {
    margin: 0 0 6px;
    font-weight: 600;
}
</style>
