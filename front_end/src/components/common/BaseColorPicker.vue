<template>
    <span class="base-color-picker" :class="[{ 'base-color-picker--empty': empty }, $attrs.class]" :style="$attrs.style">
        <span class="base-color-picker__swatch" :style="{ backgroundColor: empty ? undefined : model }">
            <i v-if="empty" class="pi pi-ban" aria-hidden="true" />
            <input class="base-color-picker__input" :aria-label="t('local.choose')" v-bind="inputAttrs()" type="color" :value="nativeColor" :disabled="disabled" @input="pickColor" @change="pickColor">
        </span>
        <button class="base-color-picker__clear" type="button" :disabled="disabled || empty" :title="t('local.clear')" :aria-label="t('local.clear')" @click="clearColor">
            <i class="pi pi-times" aria-hidden="true" />
        </button>
    </span>
</template>

<script setup lang="ts">
import 'primeicons/primeicons.css';
import tinycolor from 'tinycolor2';
import { computed, useAttrs } from 'vue';
import { useI18n } from 'vue-i18n';

const props = defineProps({ disabled: { type: Boolean, default: false } });
defineOptions({ inheritAttrs: false });
const model = defineModel({ type: String, default: 'rgba(0,0,0,0)' });
const attrs = useAttrs();
function inputAttrs() {
    const forwarded = { ...attrs };
    delete forwarded.class;
    delete forwarded.style;
    return forwarded;
}
const empty = computed(() => tinycolor(model.value).getAlpha() === 0);
const nativeColor = computed(() => tinycolor(model.value).toHexString());

function pickColor(event: Event) {
    if (!props.disabled) model.value = (event.target as HTMLInputElement).value;
}

function clearColor() {
    if (!props.disabled) model.value = 'rgba(0,0,0,0)';
}

const i18nMessages = {
    'zh-cn': { local: {
        choose: '选择颜色',
        clear: '无颜色',
    } },
    en: { local: {
        choose: 'Choose color',
        clear: 'No color',
    } },
    es: { local: {
        choose: 'Elegir color',
        clear: 'Sin color',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.base-color-picker {
    display: inline-flex;
}

.base-color-picker__swatch {
    position: relative;
    display: grid;
    place-items: center;
    flex: 1;
    min-width: 0;
}

.base-color-picker__input {
    position: absolute;
    inset: 0;
    box-sizing: border-box;
    width: 100%;
    height: 100%;
    opacity: 0;
    cursor: inherit;
}

.base-color-picker__clear {
    flex: none;
    border: 0;
    padding: 0;
    background: none;
    color: inherit;
    font: inherit;
    cursor: inherit;
}
</style>
