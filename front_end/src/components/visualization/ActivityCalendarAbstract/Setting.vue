<template>
    <span class="text-regular">{{ t('local.showDate') }}</span>&nbsp;
    <ElSwitch v-model="activityCalendarConfig.showDate" size="small" /><br>
    <span class="text-regular">{{ t('local.useEndTime') }}</span>&nbsp;
    <ElSwitch v-model="activityCalendarConfig.useEndTime" size="small" />&nbsp;
    <span :title="t('local.useEndTimeTooltip')">
        <BaseIconQuestion />
    </span><br>
    <span class="text-regular">{{ t('local.cellSize') }}</span>&nbsp;
    <ElInputNumber v-model="activityCalendarConfig.cellSize" :min="1" :max="20" size="small" controls-position="right" /><br>
    <span class="text-regular">{{ t('local.cellGap') }}</span>&nbsp;
    <ElInputNumber v-model="activityCalendarConfig.cellMargin" :min="0" :max="10" size="small" controls-position="right" />
</template>

<script setup lang="ts">
import { ElInputNumber, ElSwitch } from 'element-plus';
import { useI18n } from 'vue-i18n';

import { BaseIconQuestion } from '@/components/common/icon';
import { activityCalendarConfig } from '@/store';

/* 本地化 Localization */
const i18nMessages = {
    'zh-cn': { local: {
        cellGap: '方格间距',
        cellSize: '方格边长',
        showDate: '显示日期',
        useEndTime: '结束时间',
        useEndTimeTooltip: '依录像结束时间显示，关闭此项将使用录像上传时间。结束时间为用户的系统时间，可能不准确。',
    } },
    en: { local: {
        cellGap: 'Cell Gap',
        cellSize: 'Cell Size',
        showDate: 'Show Date',
        useEndTime: 'Display by finishing time',
        useEndTimeTooltip: 'Display by the time of finishing games when switching on, and the time of uploading when switching off. The finishing time represents the user\'s system time and can be incorrect.',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style lang="less" scoped>
.el-input-number--small {
    width: 75px;
}
</style>
