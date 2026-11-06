<template>
    <div>
        <div style="display: flex; flex-wrap: wrap; justify-content: space-between; column-gap: 2rem; row-gap: 0.25rem; align-items: center;">
            <!-- 选择排序模板 -->
            <div>
                <select v-model="BBBvSummaryConfig.template" class="base-select base-select--small" style="width: 80px" :aria-label="t('local.template')">
                    <option value="bvs">
                        {{ t('prop.bvs') }}
                    </option>
                    <option value="time">
                        {{ t('prop.time') }}
                    </option>
                    <option value="stnb">
                        {{ t('prop.stnb') }}
                    </option>
                    <option value="ioe">
                        {{ t('prop.ioe') }}
                    </option>
                    <option value="thrp">
                        {{ t('prop.thrp') }}
                    </option>
                    <option value="path">
                        {{ t('prop.path') }}
                    </option>
                    <option value="custom">
                        {{ t('local.customTemplate') }}
                    </option>
                </select>
                <template v-if="BBBvSummaryConfig.template === 'custom'">
                    &nbsp;
                    <BaseTextButton size="small" underline="always" @click="BBBvSummaryConfig.sortDesc = !BBBvSummaryConfig.sortDesc">
                        {{ BBBvSummaryConfig.sortDesc ? t('local.settingMax') : t('local.settingMin') }}
                    </BaseTextButton>
                    <select v-model="BBBvSummaryConfig.sortBy" class="base-select base-select--small" style="width:65px; margin-left: 0.2em; margin-right: 0.2em" :aria-label="t('local.sortBy')">
                        <option value="timems">
                            {{ t('prop.time') }}
                        </option>
                        <option value="ioe">
                            {{ t('prop.ioe') }}
                        </option>
                        <option value="thrp">
                            {{ t('prop.thrp') }}
                        </option>
                        <option value="path">
                            {{ t('prop.path') }}
                        </option>
                        <option value="cls">
                            {{ t('prop.cls') }}
                        </option>
                        <option value="ces">
                            {{ t('prop.ces') }}
                        </option>
                        <option value="iome">
                            {{ t('prop.iome') }}
                        </option>
                    </select>
                    <span class="text-regular text-small">
                        {{ t('local.settingDisplayBy') }}
                    </span>
                    <select v-model="BBBvSummaryConfig.displayBy" class="base-select base-select--small" style="width:8em; margin-left: 0.2em" :aria-label="t('local.displayBy')">
                        <option value="bvs">
                            {{ t('prop.bvs') }}
                        </option>
                        <option value="time">
                            {{ t('prop.time') }}
                        </option>
                        <option value="stnb">
                            {{ t('prop.stnb') }}
                        </option>
                        <option value="ioe">
                            {{ t('prop.ioe') }}
                        </option>
                        <option value="thrp">
                            {{ t('prop.thrp') }}
                        </option>
                        <option value="cls">
                            {{ t('prop.cls') }}
                        </option>
                        <option value="ces">
                            {{ t('prop.ces') }}
                        </option>
                        <option value="iome">
                            {{ t('prop.iome') }}
                        </option>
                        <option value="path">
                            {{ t('prop.path') }}
                        </option>
                        <option value="file_size">
                            {{ t('prop.file_size') }}
                        </option>
                    </select>
                </template>
            </div>
            <!-- 软件筛选 -->
            <SoftwareFilter v-model="BBBvSummaryConfig.softwareFilter" />
            <!-- 是否显示图标 -->
            <div>
                <span class="text-regular text-small">
                    {{ t('local.iconLabel') }}
                </span>
                <select v-model="BBBvSummaryConfig.showIcon" class="base-select base-select--small" style="width: 7em" :aria-label="t('local.iconLabel').trim()">
                    <option value="">
                        {{ t('local.noIcon') }}
                    </option>
                    <option value="software">
                        {{ t('prop.software') }}
                    </option>
                    <option value="state">
                        {{ t('prop.state') }}
                    </option>
                </select>
            </div>
            <!-- 高亮新录像 -->
            <div>
                <span class="text-regular text-small">
                    {{ t('local.newHighlight1') }}
                </span>
                <BaseTextButton size="small" underline="always" @click="switchNewDateField">
                    {{ t(`local.newHighlight.${BBBvSummaryConfig.newDateField}`) }}
                </BaseTextButton>
                <span class="text-regular text-small">
                    {{ t('local.newHighlight2') }}
                </span>
                <ElInputNumber v-model="BBBvSummaryConfig.newThresh" :min="0" :step="1" size="small" style="width: fit-content" />
                <span class="text-regular text-small">
                    {{ t('local.newHighlight3') }}
                </span>
            </div>
            <!-- 显示比例 -->
            <Zoomer v-model="BBBvSummaryConfig.zoom" />
        </div>
    </div>
</template>

<script setup lang="ts">
import { ElInputNumber } from 'element-plus';
import { useI18n } from 'vue-i18n';

import BaseTextButton from '@/components/common/BaseTextButton.vue';
import SoftwareFilter from '@/components/Filters/SoftwareFilter.vue';
import Zoomer from '@/components/widgets/Zoomer.vue';
import { BBBvSummaryConfig } from '@/store';

function switchNewDateField() {
    if (BBBvSummaryConfig.value.newDateField === 'upload_time') {
        BBBvSummaryConfig.value.newDateField = 'end_time';
    } else {
        BBBvSummaryConfig.value.newDateField = 'upload_time';
    }
}

/* 本地化 Localization */
const i18nMessage = {
    'zh-cn': { local: {
        customTemplate: '自定义',
        template: '模板',
        sortBy: '排序指标',
        displayBy: '显示指标',
        settingDisplayBy: '录像的',
        settingMax: '最大',
        settingMin: '最小',
        newHighlight1: '高亮',
        newHighlight2: '于',
        newHighlight3: '天内的录像',
        newHighlight: {
            end_time: '结束',
            upload_time: '上传',
        },
        iconLabel: '图标',
        noIcon: '无',
    } },
    en: { local: {
        customTemplate: 'Custom',
        template: 'Template',
        sortBy: 'Sort by',
        displayBy: 'Display by',
        settingDisplayBy: 'and display by',
        settingMax: 'Find max',
        settingMin: 'Find min',
        newHighlight1: 'Highlight videos ',
        newHighlight2: ' within ',
        newHighlight3: ' days',
        newHighlight: {
            end_time: 'finished',
            upload_time: 'uploaded',
        },
        iconLabel: 'Icon ',
        noIcon: 'None',
    } },
};

const { t } = useI18n({ messages: i18nMessage });
</script>

<style lang="less" scoped>
:deep(.el-input__inner) {
    field-sizing: content;
}
</style>
