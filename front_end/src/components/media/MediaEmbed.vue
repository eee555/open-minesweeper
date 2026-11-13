<template>
    <span class="media-embed">
        <button type="button" class="media-text-button" :aria-expanded="visible" @click="visible = !visible">
            {{ visible ? t('local.hide') : t('media.preview') }}
        </button>
        <iframe
            v-if="visible" class="media-embed-frame" :src="src" :title="t('media.preview')"
            loading="lazy" referrerpolicy="no-referrer" allowfullscreen
        />
    </span>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useI18n } from 'vue-i18n';

import '@/components/media/media.css';

defineProps({ src: { type: String, required: true } });
const visible = ref(false);

const i18nMessages = {
    'zh-cn': { local: { hide: '收起' } },
    en: { local: { hide: 'Collapse' } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>
