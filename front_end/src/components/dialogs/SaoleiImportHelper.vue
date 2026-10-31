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
        line_1: '扫雷网正在迁移，资料刷新和录像同步已关闭。',
        line_2: '账号关联仍然可用，已关联的账号和已保存的资料予以保留。',
        line_3: '您仍可通过管理按钮查看已收藏的录像和已有导入结果。',
        line_4: '已导入的录像及其上传时间不受影响。',
    } },
    en: { local: {
        line_1: 'Profile refresh and replay synchronization are disabled while Saolei.wang migrates.',
        line_2: 'Account linking remains available. Existing links and saved profiles are retained.',
        line_3: 'The Manage button still shows collected replays and existing import results.',
        line_4: 'Imported replays and their upload times are unchanged.',
    } },
};

const { t } = useI18n({
    messages: i18nMessages,
});
</script>
