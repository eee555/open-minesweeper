<template>
    <a class="link link--no-underline text" :href="`https://github.com/${props.username}`" target="_blank" rel="noopener noreferrer">
        <ElImage :src="`https://avatars.githubusercontent.com/${props.username}`" style="height: 26px; margin: 2px" />
        <span>{{ props.username }}</span>
    </a>
</template>

<script setup lang="ts" name="GitHubUser">
import '@/styles/link.css';
import { ElImage } from 'element-plus';

const props = defineProps({
    username: { type: String, required: true },
});
</script>
