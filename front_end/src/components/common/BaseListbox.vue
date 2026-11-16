<template>
    <div class="base-listbox" :role="multiple ? 'group' : 'radiogroup'" :aria-label="ariaLabel">
        <div class="base-listbox__scroll">
            <table class="base-listbox__table">
                <tbody>
                    <tr v-for="option of options" :key="String(option.value)" class="base-listbox__row" :class="{ 'base-listbox__row--selected': isSelected(option), 'base-listbox__row--disabled': disabled || option.disabled }">
                        <td class="base-listbox__cell">
                            <label class="base-listbox__option">
                                <input class="base-listbox__input" :type="multiple ? 'checkbox' : 'radio'" :name="groupName" :checked="isSelected(option)" :disabled="disabled || option.disabled" :aria-label="option.label" :data-listbox-value="String(option.value)" @change="onChange(option, $event)">
                                <span class="base-listbox__content">
                                    <slot name="option" :option="option" :selected="isSelected(option)">{{ option.label }}</slot>
                                </span>
                            </label>
                        </td>
                    </tr>
                    <tr v-if="options.length === 0 && emptyText">
                        <td class="base-listbox__empty">
                            {{ emptyText }}
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</template>

<script setup lang="ts" generic="TValue extends string | number | null, TModel extends TValue | readonly TValue[] | null">
import '@/styles/listbox.css';

import { useId } from 'vue';
import type { PropType } from 'vue';

interface ListboxOption<T> {
    value: T;
    label: string;
    disabled?: boolean;
}

const props = defineProps({
    options: {
        type: Array as PropType<readonly ListboxOption<TValue>[]>,
        required: true,
    },
    multiple: { type: Boolean, default: false },
    ariaLabel: { type: String, default: undefined },
    emptyText: { type: String, default: '' },
    disabled: { type: Boolean, default: false },
});

const model = defineModel<TModel>({ required: true });

defineSlots<{
    option?: (props: { option: ListboxOption<TValue>; selected: boolean }) => unknown;
}>();

const groupName = useId();

function isSelected(option: ListboxOption<TValue>): boolean {
    if (props.multiple) {
        return Array.isArray(model.value) && (model.value as readonly TValue[]).includes(option.value);
    }
    return Object.is(model.value, option.value);
}

function onChange(option: ListboxOption<TValue>, event: Event) {
    const { checked } = event.target as HTMLInputElement;
    if (props.multiple) {
        const current: TValue[] = Array.isArray(model.value) ? [...model.value] as TValue[] : [];
        const next: unknown = checked ? [...current, option.value] : current.filter((value) => value !== option.value);
        model.value = next as TModel;
    } else if (checked) {
        const selected: unknown = option.value;
        model.value = selected as TModel;
    }
}
</script>
