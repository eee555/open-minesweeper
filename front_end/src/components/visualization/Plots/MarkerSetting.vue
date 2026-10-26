<template>
    <Tippy trigger="click" placement="bottom-start" interactive>
        <BaseButton class="square-button" :aria-label="label">
            <svg class="marker-setting__icon" viewBox="0 0 24 24" aria-hidden="true">
                <circle
                    v-if="shape === 'circle'"
                    cx="12" cy="12" :r="iconRadius"
                    fill="currentColor" :fill-opacity="opacity"
                    stroke="currentColor" :stroke-width="iconStrokeWidth"
                />
            </svg>
        </BaseButton>

        <template #content>
            <div class="card card-small" style="overflow-x: hidden;">
                <div class="marker-setting">
                    <div v-if="hasOption('shape')" class="marker-setting__item">
                        <span class="text-regular text-small">
                            {{ t('common.prop.shape') }}
                        </span>
                        <ElSelect v-model="shape">
                            <ElOption label="Circle" value="circle" />
                        </ElSelect>
                    </div>
                    <div v-if="hasOption('radius')" class="marker-setting__item">
                        <span class="text-regular text-small">
                            {{ t('local.radius') }}
                        </span>
                        <ElInputNumber v-model="radius" size="small" :min="0" :step="1" controls-position="right" />
                    </div>
                    <div v-if="hasOption('opacity')" class="marker-setting__item">
                        <span class="text-regular text-small">
                            {{ t('local.opacity') }}
                        </span>
                        <ElSlider v-model="opacity" :min="0" :max="1" :step="0.05" />
                    </div>
                    <div v-if="hasOption('strokeWidth')" class="marker-setting__item">
                        <span class="text-regular text-small">
                            {{ t('local.strokeWidth') }}
                        </span>
                        <ElInputNumber v-model="strokeWidth" :min="0" :step="1" controls-position="right" />
                    </div>
                </div>
            </div>
        </template>
    </Tippy>
</template>

<script setup lang="ts">
import '@/styles/cards.css';
import '@/styles/text.css';

import { ElInputNumber, ElOption, ElSelect, ElSlider } from 'element-plus';
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { Tippy } from 'vue-tippy';

import BaseButton from '@/components/common/BaseButton.vue';

type MarkerShape = 'circle';
type MarkerSettingOption = 'shape' | 'radius' | 'opacity' | 'strokeWidth';

const props = defineProps({
    options: { type: String, default: 'shape radius opacity strokeWidth' },
});

const shape = defineModel<MarkerShape>('shape', { default: 'circle' });
const radius = defineModel<number>('radius', { default: 3 });
const opacity = defineModel<number>('opacity', { default: 1 });
const strokeWidth = defineModel<number>('strokeWidth', { default: 0 });

const label = 'Marker setting';
const optionSet = computed(() => new Set(props.options.split(/\s+/).filter(Boolean)));
const iconRadius = computed(() => Math.min(8, Math.max(2, radius.value)));
const iconStrokeWidth = computed(() => Math.min(5, Math.max(0, strokeWidth.value)));

function hasOption(option: MarkerSettingOption) {
    return optionSet.value.has(option);
}

const i18nMessages = {
    'zh-cn': { local: {
        opacity: '透明度',
        radius: '半径',
        strokeWidth: '描边宽度',
    } },
    en: { local: {
        opacity: 'Opacity',
        radius: 'Radius',
        strokeWidth: 'Stroke width',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style lang="less" scoped>
.marker-setting {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.marker-setting__item {
    display: flex;
    gap: 0.25em;
    align-items: center;
}

.marker-setting__icon {
    display: block;
    height: 18px;
    width: 18px;
}
</style>
