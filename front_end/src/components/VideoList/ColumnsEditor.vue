<template>
    <div class="video-columns-editor" data-cy="video-columns-editor">
        <p class="text-secondary text-small">
            {{ t(description ? 'local.sharedTooltip' : scope === 'fixed-player' ? 'local.sharedPlayer' : 'local.sharedMixed') }}
        </p>
        <p class="text-small">
            {{ t('local.help') }} <code>{{ videoExpressionFields.join(', ') }}</code>
        </p>
        <BaseTable :column-count="description ? 6 : 5" table-class="video-columns-editor__table">
            <template #head>
                <tr>
                    <th scope="col" class="video-columns-editor__actions-cell" />
                    <th scope="col" class="video-columns-editor__type-cell">
                        {{ t('local.type') }}
                    </th>
                    <th scope="col" class="video-columns-editor__key-cell">
                        {{ t('local.key') }}
                    </th>
                    <th scope="col">
                        {{ t('local.expression') }}
                    </th>
                    <th scope="col" class="video-columns-editor__preset-cell">
                        {{ t('local.preset') }}
                    </th>
                    <th v-if="description" scope="col" class="video-columns-editor__width-cell">
                        {{ t('local.width') }}
                    </th>
                </tr>
            </template>
            <tr v-for="(item, index) in draft" :key="`${item.type}:${item.id}`" data-cy="column-item">
                <td>
                    <span class="video-columns-editor__actions">
                        <BaseButton size="small" class="square-button" :title="t('local.insert')" :aria-label="t('local.insert')" data-cy="column-insert" @click="insert(index)">
                            <BaseIconAdd aria-hidden="true" />
                        </BaseButton>
                        <BaseButton size="small" class="square-button" :title="t('local.remove')" :aria-label="t('local.remove')" data-cy="column-delete" @click="remove(index)">
                            <BaseIconDelete aria-hidden="true" />
                        </BaseButton>
                    </span>
                </td>
                <td>
                    <select v-model="item.type" class="base-select base-select--small" :aria-label="t('local.type')" data-cy="column-type" @change="commit">
                        <option v-for="type in columnTypeOptions" :key="type" :value="type">
                            {{ type }}
                        </option>
                    </select>
                </td>
                <td>
                    <input v-if="hasExpression(item)" v-model="item.key" class="base-select base-select--small" :aria-label="t('local.key')" data-cy="column-key" @input="commit">
                </td>
                <td>
                    <input v-if="hasExpression(item)" v-model="item.expr" class="base-select base-select--small" :aria-label="t('local.expression')" data-cy="column-expr" @input="commit">
                    <span v-if="expressionErrors[index] !== ''" class="text-danger text-small video-columns-editor__expression-error">{{ expressionErrors[index] }}</span>
                </td>
                <td>
                    <select v-if="hasExpression(item)" class="base-select base-select--small" :aria-label="t('local.preset')" value="" data-cy="column-preset" @change="choosePreset(index, $event)">
                        <option value="">
                            —
                        </option>
                        <option v-for="field in presetOptions" :key="field" :value="field">
                            {{ videoFieldLabel(field) }}
                        </option>
                    </select>
                </td>
                <td v-if="description">
                    <select v-model.number="item.width" class="base-select base-select--small" :aria-label="t('local.width')" data-cy="column-width" @change="commit">
                        <option v-for="width in [1, 2, 3]" :key="width" :value="width">
                            {{ width }}
                        </option>
                    </select>
                </td>
            </tr>
            <tr>
                <td>
                    <BaseButton size="small" class="square-button" :title="t('local.add')" :aria-label="t('local.add')" data-cy="column-add" @click="insert(draft.length)">
                        <BaseIconAdd aria-hidden="true" />
                    </BaseButton>
                </td>
                <td :colspan="description ? 5 : 4" />
            </tr>
        </BaseTable>
        <p v-if="invalid || storageError !== ''" class="text-danger text-small" role="alert">
            {{ t(invalid || storageError === 'invalidConfig' ? 'local.invalid' : 'local.storage') }}
        </p>
    </div>
</template>

<script setup lang="ts">
import '@/styles/select.css';
import { v4 as uuidv4 } from 'uuid';
import type { PropType } from 'vue';
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { fixedColumnTypes, isFixedColumnType, isVideoColumns, videoFieldLabel } from './columns';
import type { VideoColumn, VideoColumnScope } from './columns';
import { defaultExpressionPreset, presetExpressionColumn, videoColumnPresets, videoDescriptionPresets } from './presets';

import BaseButton from '@/components/common/BaseButton.vue';
import BaseTable from '@/components/common/BaseTable.vue';
import { BaseIconAdd, BaseIconDelete } from '@/components/common/icon';
import { compileVideoExpression, videoExpressionFields } from '@/utils/videoExpression';

const props = defineProps({
    description: { type: Boolean, default: false },
    scope: { type: String as PropType<VideoColumnScope>, default: undefined },
    storageError: { type: String, default: '' },
});
const columns = defineModel<VideoColumn[]>({ required: true });
const presetOptions = computed(() => (props.description ? videoDescriptionPresets : videoColumnPresets));
const columnTypeOptions = [...fixedColumnTypes, 'data', ...Array.from({ length: 5 }, (_, digits) => `data.${digits}f`), 'date', 'bool', 'bytes'];
interface DraftColumn { id: string; type: string; key: string; expr: string; width: number }
const draft = ref<DraftColumn[]>([]);
const invalid = ref(false);
const expressionErrors = computed(() => draft.value.map((item) => (hasExpression(item) ? compileVideoExpression(item.expr).error : '')));
watch(columns, (items) => {
    draft.value = items.map((item) => ({ id: 'id' in item ? item.id : `fixed:${item.type}`, type: item.type, key: 'key' in item ? item.key : '', expr: 'expr' in item ? item.expr : '', width: 'width' in item && typeof item.width === 'number' ? item.width : 1 }));
    invalid.value = false;
}, { immediate: true });

function commit() {
    const items = draft.value.map((item) => ({
        ...isFixedColumnType(item.type) ? { type: item.type } : { id: item.id, type: item.type, key: item.key, expr: item.expr },
        ...props.description ? { width: item.width } : {},
    }));
    if (isVideoColumns(items, props.description)) {
        invalid.value = false;
        columns.value = items;
    } else invalid.value = true;
}

function insert(index: number) {
    let suffix = 1;
    while (draft.value.some((item) => item.key === `custom${suffix}`)) suffix++;
    draft.value.splice(index, 0, { ...defaultExpressionPreset, id: uuidv4(), key: `custom${suffix}`, width: 1 });
    commit();
}

function remove(index: number) {
    draft.value.splice(index, 1); commit();
}
function choosePreset(index: number, event: Event) {
    const { target } = event;
    if (!(target instanceof HTMLSelectElement) || target.value === '') return;
    const { type, key, expr } = presetExpressionColumn(target.value);
    Object.assign(draft.value[index], { type, key, expr });
    target.value = '';
    commit();
}
function hasExpression(item: DraftColumn): boolean {
    return !isFixedColumnType(item.type);
}
const i18nMessages = {
    'zh-cn': { local: {
        type: '类型',
        key: '名称',
        expression: '表达式',
        width: '宽度',
        preset: '预设',
        add: '添加到末尾',
        insert: '在此前添加',
        remove: '删除',
        sharedPlayer: '个人主页和比赛个人页共用此配置。',
        sharedMixed: '数据库检索、首页最新及待审录像共用此配置。',
        sharedTooltip: '所有录像提示共用此配置。',
        help: 'data 只输出数字；data.3f 保留三位小数；date 显示日期；bool 显示勾叉；bytes 格式化字节数。日期单位为毫秒，level 为等级代码。可用字段：',
        invalid: '类型、名称或宽度无效，或名称重复。有效修改前继续使用原配置。',
        storage: '无法保存本地配置，当前会话仍可使用。',
    } },
    en: { local: {
        type: 'Type',
        key: 'Name',
        expression: 'Expression',
        width: 'Width',
        preset: 'Preset',
        add: 'Add at end',
        insert: 'Insert before',
        remove: 'Delete',
        sharedPlayer: 'Shared by player profiles and tournament personal pages.',
        sharedMixed: 'Shared by database search, newest and review queues.',
        sharedTooltip: 'Shared by all replay tooltips.',
        help: 'data returns numbers; data.3f keeps three decimals; date formats dates; bool shows ticks/crosses; bytes formats byte counts. Dates use milliseconds; level is a code. Fields:',
        invalid: 'Invalid type, name or width, or duplicate name. The previous configuration remains active.',
        storage: 'Local storage is unavailable; changes remain usable this session.',
    } },
    es: { local: {
        type: 'Tipo',
        key: 'Nombre',
        expression: 'Expresión',
        width: 'Ancho',
        preset: 'Preajuste',
        add: 'Añadir al final',
        insert: 'Insertar antes',
        remove: 'Eliminar',
        sharedPlayer: 'Compartido por perfiles y páginas personales de torneos.',
        sharedMixed: 'Compartido por búsquedas, últimas repeticiones y cola de revisión.',
        sharedTooltip: 'Compartido por todas las vistas previas.',
        help: 'data devuelve números; data.3f usa tres decimales; date muestra fechas; bool muestra marcas; bytes formatea tamaños en bytes. Fechas en milisegundos; level es un código. Campos:',
        invalid: 'Tipo, nombre o ancho inválido, o nombre duplicado. Se mantiene la configuración anterior.',
        storage: 'No se puede guardar localmente; los cambios funcionan durante esta sesión.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.video-columns-editor {
    width: 100%;
    min-width: 0;
    max-width: 100%;
}
:deep(.video-columns-editor__table) {
    --ui-table-border-width: 0;
    --ui-table-header-background: var(--ui-table-background);
    --ui-table-header-text-color: var(--ui-table-text-color);
    --ui-table-header-font-weight: normal;
    table-layout: fixed;
    min-width: 48em;
}
.video-columns-editor__actions-cell {
    width: 5em;
}
.video-columns-editor__type-cell {
    width: 8em;
}
.video-columns-editor__key-cell {
    width: 9em;
}
.video-columns-editor__preset-cell {
    width: 10em;
}
.video-columns-editor__width-cell {
    width: 4em;
}
.video-columns-editor__actions {
    display: inline-flex;
    flex: 0 0 auto;
    gap: var(--ui-select-gap);
}
.video-columns-editor :is(input, select) {
    width: 100%;
    min-width: 0;
}
.video-columns-editor__expression-error {
    display: block;
    overflow-wrap: anywhere;
}
</style>
