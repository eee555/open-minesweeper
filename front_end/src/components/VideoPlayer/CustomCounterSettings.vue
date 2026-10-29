<template>
    <div class="custom-counter-settings" :class="{ 'custom-counter-settings--developer-mode': developerMode }">
        <div class="custom-counter-settings__toolbar">
            <label class="custom-counter-settings__number-setting">
                <span class="text-regular text-small">{{ t('local.width') }}</span>
                <InputNumber v-model="config.thWidth" :min="1" class="base-input" />
                <InputNumber v-model="config.tdWidth" :min="1" class="base-input" />
            </label>
            <label class="custom-counter-settings__number-setting">
                <span class="text-regular text-small">{{ t('local.fontSize') }}</span>
                <InputNumber v-model="config.fontSize" :min="1" class="base-input" />
            </label>
            <label class="checkbox">
                <input v-model="developerMode" class="checkbox-input" type="checkbox">
                <span class="text-small">
                    {{ t('local.developerMode') }}
                </span>
            </label>
        </div>

        <CustomCounterJsonEditor v-if="developerMode" v-model="config.table" />
        <CustomCounterRowsEditor v-else v-model="config.table" />
    </div>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import CustomCounterJsonEditor from './CustomCounterJsonEditor.vue';
import CustomCounterRowsEditor from './CustomCounterRowsEditor.vue';
import type { CustomCounterConfig } from './types';

import InputNumber from '@/components/common/InputNumber.vue';

const config = defineModel({
    type: Object as PropType<CustomCounterConfig>,
    required: true,
});

const developerMode = ref(false);

const i18nMessages = {
    'zh-cn': { local: {
        developerMode: '开发者模式',
        fontSize: '字号',
        width: '列宽',
    } },
    en: { local: {
        developerMode: 'Developer Mode',
        fontSize: 'Font Size',
        width: 'Column Widths',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.custom-counter-settings {
    display: flex;
    flex-direction: column;
    width: 40rem;
    min-width: min(100%, 40rem);
    max-height: calc(100vh - 290px);
    overflow: hidden;
}

.custom-counter-settings--developer-mode {
    height: calc(100vh - 290px);
}

.custom-counter-settings__toolbar {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;
    margin-bottom: 8px;
}

.custom-counter-settings__number-setting {
    display: flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
}

.base-input {
    field-sizing: content;
}
</style>
