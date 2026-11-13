<template>
    <ElDialog model-value :title="t('local.title')" width="min(520px, 95vw)" @close="emit('close')">
        <form class="media-submit-form" @submit.prevent="onSubmit">
            <label class="media-form-row">
                <span>{{ t('local.format') }}</span>
                <select v-model="format" class="media-input" required data-cy="submit-format">
                    <option value="B_v">{{ t('local.formatBv') }}</option>
                    <option value="B_a">{{ t('local.formatBa') }}</option>
                    <option value="c_p">{{ t('local.formatCp') }}</option>
                </select>
            </label>
            <label class="media-form-row">
                <span>{{ t('local.suffix') }}</span>
                <input
                    v-model="suffix" class="media-input" type="text" required maxlength="128"
                    :placeholder="suffixPlaceholder" data-cy="submit-suffix"
                >
            </label>
            <label class="media-form-row">
                <span>{{ t('local.language') }}</span>
                <input v-model="language" class="media-input" type="text" maxlength="32" data-cy="submit-language">
            </label>
            <p class="text-secondary text-small">
                {{ t('local.hint') }}
            </p>
            <BaseButton native-type="submit" type="primary" :loading="submitting" :disabled="submitting">
                {{ t('local.submitAction') }}
            </BaseButton>
        </form>
    </ElDialog>
</template>

<script setup lang="ts">
import { ElDialog } from 'element-plus';
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { httpErrorNotification } from '@/components/Notifications';
import { submitMedia } from '@/services/mediaService';
import type { MediaFormatValue, MediaItem } from '@/services/mediaService';

const emit = defineEmits<{ close: []; submitted: [media: MediaItem] }>();

const FORMAT_PLACEHOLDERS: Record<MediaFormatValue, string> = {
    B_v: 'BV1xx411c7mD',
    B_a: '1646742',
    c_p: '9786',
};

const format = ref<MediaFormatValue>('B_v');
const suffix = ref('');
const language = ref('');
const submitting = ref(false);
const suffixPlaceholder = computed(() => FORMAT_PLACEHOLDERS[format.value]);

async function onSubmit(): Promise<void> {
    if (submitting.value) return;
    submitting.value = true;
    try {
        const media = await submitMedia(format.value, suffix.value.trim(), language.value);
        emit('submitted', media);
    } catch (error) {
        httpErrorNotification(error);
    } finally {
        submitting.value = false;
    }
}

const i18nMessages = {
    'zh-cn': { local: {
        title: '投稿作品',
        format: '作品平台与类型',
        formatBv: 'B 站视频',
        formatBa: 'B 站专栏',
        formatCp: '扫雷网帖子',
        suffix: '作品标识',
        language: '语言（自由填写）',
        hint: '标题与发表时间由来源网站自动获取，无法获取时由管理员在审核时补全。',
        submitAction: '提交',
    } },
    en: { local: {
        title: 'Submit a work',
        format: 'Platform and type',
        formatBv: 'Bilibili video',
        formatBa: 'Bilibili article',
        formatCp: 'Saolei post',
        suffix: 'Work ID',
        language: 'Language (free text)',
        hint: 'Title and publish time are fetched from the source site; a moderator fills them in if unavailable.',
        submitAction: 'Submit',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped lang="css">
.media-submit-form {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.media-form-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 8px;
}

.media-form-row > span {
    min-width: 96px;
}

.media-input {
    flex: 1 1 240px;
    min-width: 0;
    padding: 4px 6px;
    border: 1px solid var(--ui-border-color);
    border-radius: 0;
    background: var(--ui-bg-color);
    color: var(--ui-text-color-regular);
    font: inherit;
}

.media-input:focus-visible {
    outline: 2px solid var(--ui-color-primary);
}
</style>
