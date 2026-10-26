<template>
    <ElDialog v-model="visible" :title="creating ? t('local.add') : `${t('local.edit')}: ${event.key}`" width="min(520px, calc(100vw - 24px))" append-to-body @closed="emit('close')">
        <form id="custom-event-editor-form" class="custom-event-editor" @submit.prevent="save">
            <label><span>key</span><input v-model="draft.key" class="base-input custom-event-editor__key" required @input="validationError = ''"></label>
            <label><span>{{ t('common.prop.expression') }}</span><textarea v-model="draft.expression" class="base-input custom-event-editor__expression" rows="3" /></label>
            <div class="custom-event-editor__field">
                <span>{{ t('local.type') }}</span>
                <div class="button-group button-group--joined custom-event-editor__types" role="group" :aria-label="t('local.type')">
                    <BaseButton v-for="type in ['pulse', 'sustained'] as const" :key="type" :aria-pressed="draft.type === type" :type="draft.type === type ? 'primary' : 'default'" @click="draft.type = type">
                        {{ t(`local.${type}`) }}
                    </BaseButton>
                </div>
            </div>
            <label><span>{{ t('common.prop.color') }}</span><BaseColorPicker v-model="draft.color" class="custom-event-editor__color" /></label>
            <template v-if="draft.type === 'pulse'">
                <label><span>{{ t('local.shape') }}</span><select v-model="draft.marker.shape" class="custom-event-editor__shape"><option v-for="shape in eventMarkerShapes" :key="shape" :value="shape">{{ t(`local.${shape}`) }}</option></select></label>
                <label><span>{{ t('local.size') }} (px)</span><InputNumber v-model="draft.marker.size" class="custom-event-editor__marker-size" :min="1" :step="1" /></label>
                <label><span>{{ t('common.prop.opacity') }}</span><InputNumber v-model="draft.marker.opacity" :min="0" :max="1" :step="0.01" /></label>
            </template>
            <template v-else>
                <label><span>{{ t('local.lineStyle') }}</span><select v-model="draft.line.style" class="custom-event-editor__line-style"><option v-for="style in eventLineStyles" :key="style" :value="style">{{ t(`local.${style}`) }}</option></select></label>
                <label><span>{{ t('local.width') }} (px)</span><InputNumber v-model="draft.line.width" :min="0.1" :step="0.1" /></label>
                <label><span>{{ t('common.prop.opacity') }}</span><InputNumber v-model="draft.line.opacity" :min="0" :max="1" :step="0.01" /></label>
            </template>
            <CounterExpressionHelp />
            <output class="contains custom-event-editor__preview" aria-live="polite">{{ t('local.occurrences', { count: draft.type === 'pulse' ? preview.pulses.length : preview.spans.length }) }}</output>
            <p v-if="validationError" class="contains text-danger" role="alert">
                {{ validationError }}
            </p>
        </form>
        <template #footer>
            <div class="custom-event-editor__footer">
                <BaseButton v-if="!creating" class="custom-event-editor__delete" :title="t('local.remove')" :aria-label="t('local.remove')" @click="emit('remove')">
                    <i class="pi pi-trash" aria-hidden="true" />
                </BaseButton>
                <div class="button-group button-group--joined">
                    <BaseButton class="custom-event-editor__cancel" @click="visible = false">
                        {{ t('common.button.cancel') }}
                    </BaseButton>
                    <BaseButton class="custom-event-editor__save" type="primary" native-type="submit" form="custom-event-editor-form">
                        {{ t('common.button.save') }}
                    </BaseButton>
                </div>
            </div>
        </template>
    </ElDialog>
</template>

<script setup lang="ts">
import { ElDialog } from 'element-plus';
import { computed, ref } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import type { CounterEvent } from './counter';
import CounterExpressionHelp from './CounterExpressionHelp.vue';
import { eventLineStyles, eventMarkerShapes, prepareCustomEvents } from './customEvents';
import type { CustomEventDefinition } from './customEvents';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseColorPicker from '@/components/common/BaseColorPicker.vue';
import InputNumber from '@/components/common/InputNumber.vue';

const props = defineProps({
    event: { type: Object as PropType<CustomEventDefinition>, required: true },
    creating: { type: Boolean, required: true },
    existingKeys: { type: Array as PropType<string[]>, required: true },
    events: { type: Array as PropType<CounterEvent[]>, required: true },
    durationMs: { type: Number, required: true },
});
const emit = defineEmits<{ save: [event: CustomEventDefinition]; remove: []; close: [] }>();
const visible = ref(true);
const draft = ref({ ...props.event, marker: { ...props.event.marker }, line: { ...props.event.line } });
const validationError = ref('');
const preview = computed(() => prepareCustomEvents([draft.value], props.events, props.durationMs).get(draft.value.key) ?? { pulses: [], spans: [] });

function save() {
    const key = draft.value.key.trim();
    if (key === '' || props.existingKeys.includes(key)) {
        validationError.value = t(key === '' ? 'local.requiredKey' : 'local.duplicateKey');
        return;
    }
    emit('save', { ...draft.value, key, marker: { ...draft.value.marker }, line: { ...draft.value.line } });
    visible.value = false;
}

const i18nMessages = {
    'zh-cn': { local: {
        add: '添加自定义事件',
        edit: '编辑自定义事件',
        type: '类型',
        pulse: '脉冲',
        sustained: '持续',
        shape: '标记形状',
        size: '棋盘标记大小',
        lineStyle: '线型',
        width: '线宽',
        solid: '实线',
        dash: '虚线',
        dot: '点线',
        circle: '圆形',
        square: '方形',
        triangle: '三角形',
        diamond: '菱形',
        cross: '叉形',
        occurrences: '发生次数：{count}',
        requiredKey: '事件 key 不能为空',
        duplicateKey: '自定义事件 key 不能重复',
        remove: '删除事件',
    } },
    en: { local: {
        add: 'Add custom event',
        edit: 'Edit custom event',
        type: 'Type',
        pulse: 'Pulse',
        sustained: 'Sustained',
        shape: 'Marker shape',
        size: 'Board marker size',
        lineStyle: 'Line style',
        width: 'Line width',
        solid: 'Solid',
        dash: 'Dashed',
        dot: 'Dotted',
        circle: 'Circle',
        square: 'Square',
        triangle: 'Triangle',
        diamond: 'Diamond',
        cross: 'Cross',
        occurrences: 'Occurrences: {count}',
        requiredKey: 'Event key is required',
        duplicateKey: 'Custom event keys must be unique',
        remove: 'Delete event',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.custom-event-editor {
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.custom-event-editor label,
.custom-event-editor__field {
    display: grid;
    grid-template-columns: 8em minmax(0, 1fr);
    align-items: center;
    gap: 8px;
}
.custom-event-editor input,
.custom-event-editor textarea,
.custom-event-editor select {
    min-width: 0;
    font: inherit;
    color: var(--ui-text-color-primary);
    background: var(--ui-bg-color);
}
.custom-event-editor textarea {
    resize: vertical;
    overflow-wrap: anywhere;
}
.custom-event-editor__types {
    display: flex;
}
.custom-event-editor__types > * {
    flex: 1;
}
.custom-event-editor__color {
    width: 100%;
    max-width: 180px;
    height: 22px;
}
.custom-event-editor__delete {
    margin-right: auto;
}
.custom-event-editor__footer {
    display: flex;
    justify-content: flex-end;
}
</style>
