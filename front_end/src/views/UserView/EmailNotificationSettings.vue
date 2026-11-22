<template>
    <section class="email-notifications">
        <h2 class="text-large">
            {{ t('local.title') }}
        </h2>
        <template v-if="store.user.is_staff">
            <p class="text-regular text-small">
                {{ t('local.description') }}
            </p>
            <fieldset :disabled="saving" class="email-notifications__options">
                <legend class="text-small">
                    {{ t('local.staffNotifications') }}
                </legend>
                <label v-for="item in emailNotificationTypes" :key="item.type">
                    <input v-model="selected[item.type]" type="checkbox" :name="item.type">
                    {{ t(`local.${item.type}`) }}
                </label>
            </fieldset>
            <BaseButton size="small" :loading="saving" :disabled="!hasChanges" @click="save">
                {{ t('button.save') }}
            </BaseButton>
        </template>
        <p v-else class="text-regular text-small">
            {{ t('local.unavailable') }}
        </p>
    </section>
</template>

<script setup lang="ts">
import { isAxiosError } from 'axios';
import { computed, onScopeDispose, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { actionSuccessNotification, baseErrorNotification } from '@/components/Notifications';
import { emailNotificationTypes, saveEmailNotifications } from '@/services/emailNotificationService';
import type { EmailNotificationType } from '@/services/emailNotificationService';
import { store } from '@/store';

const selected = reactive<Record<EmailNotificationType, boolean>>({
    staff_media_review: false,
    staff_video_frozen: false,
    staff_video_plain: false,
    staff_account_link_review: false,
    staff_identifier_unsafe: false,
});
const saving = ref(false);
let requestVersion = 0;
const changes = computed(() => emailNotificationTypes.filter(({ type, flag }) => selected[type] !== ((store.user.email_notification_mask & flag) !== 0)).map(({ type }) => ({ type, enabled: selected[type] })));
const hasChanges = computed(() => changes.value.length > 0);

watch([() => store.user.id, () => store.sessionRevision, () => store.user.email_notification_mask], () => {
    requestVersion++;
    saving.value = false;
    for (const { type, flag } of emailNotificationTypes) selected[type] = (store.user.email_notification_mask & flag) !== 0;
}, { immediate: true, flush: 'sync' });

async function save(): Promise<void> {
    if (saving.value || !store.user.is_staff || !hasChanges.value) return;
    const version = ++requestVersion;
    const userId = store.user.id;
    const revision = store.sessionRevision;
    const isCurrent = () => version === requestVersion && userId === store.user.id && revision === store.sessionRevision;
    saving.value = true;
    try {
        const mask = await saveEmailNotifications(changes.value);
        if (!isCurrent()) return;
        store.user.email_notification_mask = mask;
        actionSuccessNotification();
    } catch (error) {
        if (!isCurrent()) return;
        baseErrorNotification(t('msg.actionFail'), t(isAxiosError(error) && error.response?.status === 409 ? 'local.emailRequired' : 'local.saveError'));
    } finally {
        if (isCurrent()) saving.value = false;
    }
}

onScopeDispose(() => { requestVersion++; });

const i18nMessages = {
    'zh-cn': { local: {
        title: '邮件通知',
        description: '通知发送至账号邮箱。邮件包含中文、英文和西班牙语，可能偶发漏发；待办请以网站为准。',
        staffNotifications: '管理员通知',
        staff_media_review: '作品待审核',
        staff_video_frozen: '录像冻结（FROZEN）',
        staff_video_plain: '录像需要审核（PLAIN）',
        staff_account_link_review: '账号关联申请',
        staff_identifier_unsafe: '新标识自动审核未通过',
        unavailable: '暂无可订阅的邮件通知类型。',
        emailRequired: '当前账号没有可接收邮件的邮箱，无法开启通知。',
        saveError: '邮件通知设置保存失败，请稍后重试。',
    } },
    en: { local: {
        title: 'Email notifications',
        description: 'Notifications go to your account email and include Chinese, English and Spanish. Delivery may occasionally fail; check the website for pending items.',
        staffNotifications: 'Staff notifications',
        staff_media_review: 'Media awaiting review',
        staff_video_frozen: 'Video frozen (FROZEN)',
        staff_video_plain: 'Video awaiting review (PLAIN)',
        staff_account_link_review: 'Account link requests',
        staff_identifier_unsafe: 'New identifier failed automatic review',
        unavailable: 'No email notification types are available yet.',
        emailRequired: 'This account has no deliverable email address, so notifications cannot be enabled.',
        saveError: 'Could not save email notification settings. Please try again later.',
    } },
    es: { local: {
        title: 'Notificaciones por correo',
        description: 'Las notificaciones se envían al correo de tu cuenta e incluyen chino, inglés y español. Puede haber fallos ocasionales; consulta los pendientes en el sitio web.',
        staffNotifications: 'Notificaciones de administración',
        staff_media_review: 'Obra pendiente de revisión',
        staff_video_frozen: 'Vídeo congelado (FROZEN)',
        staff_video_plain: 'Vídeo pendiente de revisión (PLAIN)',
        staff_account_link_review: 'Solicitudes de vinculación de cuentas',
        staff_identifier_unsafe: 'Nuevo identificador rechazado en la revisión automática',
        unavailable: 'Todavía no hay tipos de notificación disponibles.',
        emailRequired: 'Esta cuenta no tiene un correo válido para recibir notificaciones.',
        saveError: 'No se pudo guardar la configuración. Inténtalo de nuevo más tarde.',
    } },
};
const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped>
.email-notifications h2 {
    margin: 0 0 0.5rem;
}

.email-notifications__options {
    display: grid;
    gap: 0.35rem;
    margin: 0 0 0.5rem;
    padding: 0.5rem;
    border: 1px solid var(--el-border-color);
}

.email-notifications__options label {
    display: flex;
    align-items: center;
    gap: 0.35rem;
}

.email-notifications__options input {
    margin: 0;
    accent-color: var(--el-color-primary);
}
</style>
