<template>
    <section class="email-notifications">
        <h2 class="text text-large">
            {{ t('local.title') }}
        </h2>
        <label class="email-notifications__language">
            <span class="text-small">{{ t('local.language') }}</span>
            <select v-model="language" name="language" class="base-select base-select--small" :disabled="saving">
                <option v-for="item in emailNotificationLanguages" :key="item.lang" :value="item.lang">{{ item.text }}</option>
            </select>
        </label>
        <template v-if="store.user.is_staff">
            <p class="text text-secondary text-small">
                {{ t('local.description') }}
            </p>
            <fieldset :disabled="saving" class="email-notifications__options">
                <legend class="text text-secondary text-small">
                    {{ t('local.staffNotifications') }}
                </legend>
                <div class="checkbox-group">
                    <label v-for="item in emailNotificationTypes" :key="item.type" class="checkbox">
                        <input v-model="selected[item.type]" class="checkbox-input" type="checkbox" :name="item.type">
                        <span>{{ t(`local.${item.type}`) }}</span>
                    </label>
                </div>
            </fieldset>
        </template>
        <p v-else class="text text-secondary text-small">
            {{ t('local.unavailable') }}
        </p>
        <BaseButton size="small" :loading="saving" :disabled="!hasChanges" @click="save">
            {{ t('button.save') }}
        </BaseButton>
    </section>
</template>

<script setup lang="ts">
import { isAxiosError } from 'axios';
import { computed, onScopeDispose, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import { actionSuccessNotification, baseErrorNotification } from '@/components/Notifications';
import { offlineLanguages as emailNotificationLanguages } from '@/i18n/language';
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
const language = ref(store.user.language);
let requestVersion = 0;
const changes = computed(() => (store.user.is_staff ? emailNotificationTypes.filter(({ type, flag }) => selected[type] !== ((store.user.email_notification_mask & flag) !== 0)).map(({ type }) => ({ type, enabled: selected[type] })) : []));
const hasChanges = computed(() => changes.value.length > 0 || language.value !== store.user.language);

watch([() => store.user.id, () => store.sessionRevision, () => store.user.email_notification_mask, () => store.user.language, () => store.user.is_staff], () => {
    requestVersion++;
    saving.value = false;
    language.value = store.user.language;
    for (const { type, flag } of emailNotificationTypes) selected[type] = (store.user.email_notification_mask & flag) !== 0;
}, { immediate: true, flush: 'sync' });

async function save(): Promise<void> {
    if (saving.value || !hasChanges.value) return;
    const version = ++requestVersion;
    const userId = store.user.id;
    const revision = store.sessionRevision;
    const isCurrent = () => version === requestVersion && userId === store.user.id && revision === store.sessionRevision;
    saving.value = true;
    try {
        const settings = await saveEmailNotifications({
            ...changes.value.length > 0 ? { changes: changes.value } : {},
            ...language.value !== store.user.language ? { language: language.value } : {},
        });
        if (!isCurrent()) return;
        Object.assign(store.user, settings);
        actionSuccessNotification();
    } catch (error) {
        if (!isCurrent()) return;
        baseErrorNotification(t('msg.actionFail'), t(isAxiosError(error) && error.response?.status === 409 ? 'local.emailRequired' : 'local.saveError'));
    } finally {
        if (isCurrent()) saving.value = false;
    }
}

onScopeDispose(() => {
    requestVersion++;
});

const i18nMessages = {
    'zh-cn': { local: {
        title: '邮件通知',
        language: '通知语言',
        description: '通知发送至账号邮箱。可能偶发漏发；待办请以网站为准。',
        staffNotifications: '管理员通知',
        staff_media_review: '作品待审核',
        staff_video_frozen: '录像冻结',
        staff_video_plain: '录像需要审核',
        staff_account_link_review: '账号关联申请',
        staff_identifier_unsafe: '新标识自动审核未通过',
        unavailable: '暂无可订阅的邮件通知类型。',
        emailRequired: '当前账号没有可接收邮件的邮箱，无法开启通知。',
        saveError: '邮件通知设置保存失败，请稍后重试。',
    } },
    en: { local: {
        title: 'Email notifications',
        language: 'Notification language',
        description: 'Notifications go to your account email. Delivery may occasionally fail; check the website for pending items.',
        staffNotifications: 'Staff notifications',
        staff_media_review: 'Media awaiting review',
        staff_video_frozen: 'Video frozen',
        staff_video_plain: 'Video awaiting review',
        staff_account_link_review: 'Account link requests',
        staff_identifier_unsafe: 'New identifier failed automatic review',
        unavailable: 'No email notification types are available yet.',
        emailRequired: 'This account has no deliverable email address, so notifications cannot be enabled.',
        saveError: 'Could not save email notification settings. Please try again later.',
    } },
    es: { local: {
        title: 'Notificaciones por correo',
        language: 'Idioma de las notificaciones',
        description: 'Las notificaciones se envían al correo de tu cuenta. Puede haber fallos ocasionales; consulta los pendientes en el sitio web.',
        staffNotifications: 'Notificaciones de administración',
        staff_media_review: 'Obra pendiente de revisión',
        staff_video_frozen: 'Vídeo congelado',
        staff_video_plain: 'Vídeo pendiente de revisión',
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
.email-notifications {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
}

.email-notifications__options {
    align-self: stretch;
    min-width: 0;
    margin: 0;
    border: 1px solid var(--ui-border-color);
    padding: 4px 8px 8px;
}

.email-notifications__language {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
}
</style>
