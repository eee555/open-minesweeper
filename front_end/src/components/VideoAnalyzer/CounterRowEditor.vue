<template>
    <ElDialog v-model="visible" :title="creating ? t('local.add') : `${t('button.edit')}: ${row.key}`" width="min(480px, calc(100vw - 24px))" append-to-body @closed="emit('close')">
        <form id="counter-row-editor-form" class="counter-row-editor" @submit.prevent="save">
            <label v-if="creating"><span>key</span><input v-model="draft.key" class="base-input counter-row-editor__key" type="text" required @input="validationError = ''"></label>
            <label><span>{{ t('prop.expression') }}</span><input v-model="draft.expression" class="base-input counter-row-editor__expression" type="text"></label>
            <label><span>{{ t('local.format') }}</span><input v-model="draft.format" class="base-input counter-row-editor__format" type="text"></label>
            <label><span>{{ t('local.sampling') }}</span><select v-model="draft.samplingMode" class="counter-row-editor__sampling"><option v-for="mode in samplingModes" :key="mode" :value="mode">{{ t(`local.${mode}`) }}</option></select></label>
            <CounterExpressionHelp />
            <output v-if="events.length" class="contains counter-row-editor__preview" :class="{ 'text-danger': preview.error }" aria-live="polite">{{ preview.value }}</output>
            <p v-if="validationError" class="contains text-danger" role="alert">
                {{ validationError }}
            </p>
        </form>
        <template #footer>
            <div class="button-group button-group--joined counter-row-editor__actions">
                <BaseButton class="counter-row-editor__cancel" @click="visible = false">
                    {{ t('button.cancel') }}
                </BaseButton>
                <BaseButton class="counter-row-editor__save" type="primary" native-type="submit" form="counter-row-editor-form">
                    {{ t('button.save') }}
                </BaseButton>
            </div>
        </template>
    </ElDialog>
</template>

<script setup lang="ts">
import { ElDialog } from 'element-plus';
import { computed, ref } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import { displayCounter, prepareCounter, samplingModes } from './counter';
import type { CounterEvent, CounterRow } from './counter';
import CounterExpressionHelp from './CounterExpressionHelp.vue';

import BaseButton from '@/components/common/BaseButton.vue';

const props = defineProps({
    row: { type: Object as PropType<CounterRow>, required: true },
    events: { type: Array as PropType<CounterEvent[]>, required: true },
    currentMs: { type: Number, required: true },
    durationMs: { type: Number, default: undefined },
    creating: { type: Boolean, default: false },
    existingKeys: { type: Array as PropType<string[]>, default: () => [] },
});
const emit = defineEmits<{ save: [row: CounterRow]; close: [] }>();
const visible = ref(true);
const draft = ref({ ...props.row });
const validationError = ref('');
const prepared = computed(() => prepareCounter(draft.value, props.events, props.durationMs));
const preview = computed(() => displayCounter(prepared.value, props.currentMs));

function save() {
    if (props.creating && props.existingKeys.includes(draft.value.key)) {
        validationError.value = t('local.duplicateKey');
        return;
    }
    emit('save', { ...draft.value });
    visible.value = false;
}

const i18nMessages = {
    'zh-cn': { local: {
        add: '添加计数器行',
        duplicateKey: '行 key 不能重复',
        format: '数字格式',
        sampling: '采样模式',
        continuous: '连续采样',
        button: '每个按键事件',
        board: '每次局面变化',
    } },
    en: { local: {
        add: 'Add counter row',
        duplicateKey: 'Row keys must be unique',
        format: 'Number format',
        sampling: 'Sampling mode',
        continuous: 'Continuous sampling',
        button: 'Every button event',
        board: 'Every board change',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.counter-row-editor__actions {
    justify-content: flex-end;
}
.counter-row-editor {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.counter-row-editor label {
    display: grid;
    grid-template-columns: 7em minmax(0, 1fr);
    align-items: center;
    gap: 8px;
}

.counter-row-editor input,
.counter-row-editor select {
    min-width: 0;
    font: inherit;
    color: var(--el-text-color-primary);
    background: var(--el-bg-color);
}

.counter-row-editor__preview {
    overflow-wrap: anywhere;
    font-variant-numeric: tabular-nums;
}
</style>
