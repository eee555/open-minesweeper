<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useData, withBase } from 'vitepress';

import { docLocales, isDocLocale, languageNames, missingTitles } from '../../locales';

const availableText = { zh: '可使用以下语言阅读此页面：', en: 'You can read this page in:', es: 'Puedes leer esta página en los siguientes idiomas:' };
const { page, theme, hash } = useData();
const path = computed(() => page.value.relativePath.replace(/^(zh|en|es)\//, '').replace(/(^|\/)index\.md$/, '$1').replace(/\.md$/, ''));
const locales = computed(() => docLocales.filter((locale) => theme.value.localizedPages[locale].includes(path.value)));
const missingLocale = computed(() => {
    const first = page.value.relativePath.split('/')[0];
    return isDocLocale(first) ? first : undefined;
});
const suffix = ref('');

onMounted(() => {
    watch([page, hash], () => {
        suffix.value = window.location.search + window.location.hash;
    }, { immediate: true });
});
</script>

<template>
    <div class="locale-page vp-doc">
        <template v-if="missingLocale">
            <h1>{{ missingTitles[missingLocale] }}</h1>
            <p>{{ availableText[missingLocale] }}</p>
        </template>
        <p v-else>正在根据浏览器语言跳转…… / Redirecting to your browser language… / Redirigiendo al idioma de tu navegador…</p>
        <ul>
            <li v-for="locale in locales" :key="locale"><a :href="withBase(`/${locale}/${path}${suffix}`)">{{ languageNames[locale] }}</a></li>
        </ul>
    </div>
</template>

<style scoped>
.locale-page {
    max-width: 720px;
    margin: 0 auto;
    padding: 32px 24px;
}
</style>
