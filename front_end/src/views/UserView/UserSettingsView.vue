<template>
    <div v-if="canEdit" class="layout-stack user-settings">
        <section>
            <h2 class="text-large">
                {{ t('local.profile') }}
            </h2>
            <ProfileQualification />
            <EditProfile :key="user.id" v-model:user="user" :exp-time-ms="store.expTimeMs" :qualification-status="store.qualificationStatus" />
        </section>
        <section>
            <h2 class="text-large">
                {{ t('identifierManager.title') }}
                <BaseOverlay>
                    <BaseIconInfo />
                    <template #overlay>
                        <IdentifierHelper style="width: 60%; min-width: 400px; max-width: 100%; margin: auto; display: block" />
                    </template>
                </BaseOverlay>
            </h2>
            <IdentifierManager v-model:user="user" @identifiers-changed="invalidateProfileData(user.id)" />
        </section>
    </div>
</template>

<script setup lang="ts">
import '@/styles/layout.css';
import { computed, defineAsyncComponent, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import EditProfile from './EditProfile.vue';
import ProfileQualification from './ProfileQualification.vue';

import BaseOverlay from '@/components/common/BaseOverlay.vue';
import { BaseIconInfo } from '@/components/common/icon';
import IdentifierManager from '@/components/widgets/IdentifierManager.vue';
import { invalidateProfileData } from '@/services/profileDataService';
import { store } from '@/store';
import { LoginStatus } from '@/utils/common/structInterface';
import { UserProfile } from '@/utils/userprofile';

const IdentifierHelper = defineAsyncComponent(() => import('@/components/dialogs/IdentifierHelper.vue'));
const user = defineModel('user', { type: UserProfile, required: true });
const route = useRoute();
const router = useRouter();
const canEdit = computed(() => store.isSelf && Number(route.params.id) === store.user.id);

watch([() => route.name, () => route.params.id, () => store.login_status, canEdit], () => {
    if (route.name === 'user-settings' && store.login_status !== LoginStatus.Undefined && !canEdit.value) {
        void router.replace({ name: 'user-top', params: { id: route.params.id } });
    }
}, { immediate: true });

const i18nMessages = {
    'zh-cn': { local: { profile: '个人资料' } },
    en: { local: { profile: 'Profile' } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.user-settings {
    max-width: 48rem;
}

h2 {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 0 0 0.5rem;
}
</style>
