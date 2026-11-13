<template>
    <div class="account-link-main">
        <AccountPage v-if="active" :key="context" :user-id="userId" />
    </div>
</template>

<script setup lang="ts">
import { computed, onActivated, onDeactivated, ref } from 'vue';

import AccountPage from './AccountPage.vue';

import { store } from '@/store';

const props = defineProps({ userId: { type: Number, default: 0 } });
const active = ref(true);
const context = computed(() => `${props.userId}:${store.sessionRevision}:${store.user.id}:${store.user.is_staff}:${store.user.is_superuser}:${store.player?.is_memorial}`);
onActivated(() => {
    active.value = true;
});
onDeactivated(() => {
    active.value = false;
});
</script>
