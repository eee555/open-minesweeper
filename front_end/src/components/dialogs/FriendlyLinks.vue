<!-- 已弃用 -->

<template>
    <span class="text-button" @click="centerDialogVisible = true;">{{ t('local.networkLinks') }}</span>
    <ElDialog v-if="centerDialogVisible" model-value :title="t('local.networkLinks')" width="50%" align-center draggable :lock-scroll="false" @closed="centerDialogVisible = false">
        <ul>
            <li>
                <a target="_blank" href="https://gitee.com/ee55/saolei_website/issues" rel="noopener noreferrer">{{ t('local.gitee') }}</a>
                <span>{{ t('local.giteeHint') }}</span>
            </li>
            <li>
                <a target="_blank" href="https://github.com/eee555/saolei_website" rel="noopener noreferrer">{{ t('local.github') }}</a>
                <span>{{ t('local.githubHint') }}</span>
            </li>
            <li>
                <a target="_blank" href="http://www.saolei.wang/" rel="noopener noreferrer">{{ t('local.saolei') }}</a>
                <span>{{ t('local.national') }}</span>
            </li>
            <li>
                <a target="_blank" href="https://minesweepergame.com/world-rankings.php" rel="noopener noreferrer">The Authoritative Minesweeper</a>
                <span>{{ t('local.international') }}</span>
            </li>
        </ul>

        <template #footer>
            <span class="dialog-footer">
                <BaseButtonConfirm @click="centerDialogVisible = false" />
            </span>
        </template>
    </ElDialog>
</template>

<script lang="ts" setup>
// 注册、登录的弹框及右上方按钮
import { ElDialog } from 'element-plus';
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButtonConfirm from '@/components/common/BaseButtonConfirm.vue';

const i18nMessages = {
    'zh-cn': { local: {
        giteeHint: '（反馈网站bug、提供建议、参与提案的讨论）',
        githubHint: '（了解最新进展、加入开发团队、提供赞助）',
        national: '（老牌的国内扫雷记录排名网站）',
        international: '（老牌的国际扫雷记录排名网站）',
        github: '本站Github主页',
        gitee: '本站码云主页',
        saolei: '扫雷网',
        networkLinks: '友链',
    } },
    en: { local: {
        giteeHint: '(report bugs, suggest changes and discuss proposals)',
        githubHint: '(follow development, join the team or sponsor the project)',
        national: '(long-running Chinese Minesweeper rankings)',
        international: '(long-running international Minesweeper rankings)',
        github: 'Project on GitHub',
        gitee: 'Project on Gitee',
        saolei: 'Saolei.wang',
        networkLinks: 'Related sites',
    } },
    es: { local: {
        giteeHint: '(comunica fallos, sugiere cambios y debate propuestas)',
        githubHint: '(sigue el desarrollo, únete al equipo o patrocina el proyecto)',
        national: '(clasificación histórica china de Buscaminas)',
        international: '(clasificación histórica internacional de Buscaminas)',
        github: 'Proyecto en GitHub',
        gitee: 'Proyecto en Gitee',
        saolei: 'Saolei.wang',
        networkLinks: 'Sitios relacionados',
    } },
};
const { t } = useI18n({ messages: i18nMessages });

const centerDialogVisible = ref(false);
</script>

<style scoped>
a {
    color: blue;
}
</style>
