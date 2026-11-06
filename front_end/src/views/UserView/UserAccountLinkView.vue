<template>
    <AccountLinks :user-id="store.player.id" />
</template>

<script setup lang="ts">
import AccountLinks from './AccountLinks/App.vue';

import { store } from '@/store';
</script>
