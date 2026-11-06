<template>
    <div class="text-medium">
        <ul>
            <li>
                {{ t('local.line_1') }}
            </li>
            <li>
                {{ t('local.line_2') }}
            </li>
            <li>
                {{ t('local.line_3') }}
            </li>
            <li>
                {{ t('local.line_4') }}
            </li>
        </ul>
    </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n';

const i18nMessages = {
    'zh-cn': { local: {
        line_1: '已绑定账号默认每日更新目录，每小时最多自动导入100个录像，可自行关闭。',
        line_2: '手动同步先更新录像目录，再依次导入未完成的录像，请保持窗口打开。',
        line_3: '仅接受 Clone、Vienna、Arbiter、元扫雷。导入失败的录像不再自动重试。',
        line_4: '同步中断后可继续；已导入的录像保持原有关联和审核结果。',
    } },
    en: { local: {
        line_1: 'Linked accounts update their catalogue daily and import up to 100 replays each hour by default. You can disable this.',
        line_2: 'Manual sync updates the catalogue, then imports pending replays sequentially. Keep the window open.',
        line_3: 'Only Clone, Vienna, Arbiter and 元扫雷 are supported. Replays that fail to import are not retried automatically.',
        line_4: 'Interrupted sync can resume. Existing imports keep their links and review results.',
    } },
};

const { t } = useI18n({
    messages: i18nMessages,
});
</script>
