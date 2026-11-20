<template>
    <input ref="fileInputRef" type="file" accept="image/jpeg,image/png,image/gif,image/webp" style="display: none" @change="handleFileChange">
    <img
        v-loading="updating"
        :src="avatarSrc"
        :disabled="disabled"
        :title="avatarTitle"
        style="max-height: 100%; max-width: 100%; aspect-ratio: 1 / 1; border-radius: 50%;"
        sizes="auto"
        @click="triggerFileDialog"
        @error="avatarSrc = DefaultAvatar"
    >
</template>

<script setup lang="ts">
import { vLoading } from 'element-plus';
import { computed, ref, useTemplateRef, watch } from 'vue';
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import { baseErrorNotification, httpErrorNotification } from '@/components/Notifications';
import { DefaultAvatar } from '@/utils/assets';
import useCurrentInstance from '@/utils/common/useCurrentInstance';
import { globalNow, toISODateTimeString } from '@/utils/datetime';
import { UserProfile } from '@/utils/userprofile';

const props = defineProps({
    isSelf: { type: Boolean, default: false },
    expTimeMs: { type: Number, default: 999999 },
    qualificationStatus: { type: String as PropType<'idle' | 'loading' | 'ready' | 'error'>, default: 'ready' },
});

const { proxy } = useCurrentInstance();

const user = defineModel<UserProfile>('user', { type: UserProfile, default: () => new UserProfile() });

const avatarVersion = ref(0);
const avatarSrc = ref(DefaultAvatar);

function refresh(newId: number) {
    if (newId) {
        avatarSrc.value = `${proxy.$axios.defaults.baseURL}/api/userprofile/avatar/${newId}?v=${avatarVersion.value}`;
    } else {
        avatarSrc.value = DefaultAvatar;
    }
}

watch(() => user.value.id, refresh, { immediate: true });

const fileInputRef = useTemplateRef<HTMLInputElement>('fileInputRef');
function triggerFileDialog() {
    if (disabled.value) return;
    fileInputRef.value?.click();
}

async function handleFileChange(event: Event) {
    if (updating.value) return;
    updating.value = true;

    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;

    const maxSize = 300 * 1024;
    if (file.size > maxSize) {
        baseErrorNotification(t('local.errorTitle'), t('local.errorMsg.avatar.oversize'));
        updating.value = false;
        return;
    }

    await updateAvatar(file);
    updating.value = false;
}

const avatarBudget = computed(() => user.value.newAvatarBudget(globalNow.value));
const avatarTitle = computed(() => {
    if (!props.isSelf) return undefined;
    if (props.qualificationStatus === 'error') return t('local.qualificationError');
    if (props.qualificationStatus !== 'ready') return t('local.qualificationLoading');
    if (props.expTimeMs >= 200000) return t('local.tooltipExpTime');
    if (avatarBudget.value > 0) return t('local.tooltipBase', [avatarBudget.value]);
    return `${t('local.tooltipCooldown')}${toISODateTimeString(user.value.nextAvatarAvailable)}`;
});

const updating = ref(false);
const disabled = computed(() => !props.isSelf || props.qualificationStatus !== 'ready' || props.expTimeMs >= 200000 || avatarBudget.value <= 0);

async function updateAvatar(a: File) {
    const formData = new FormData();
    formData.append('avatar', a);
    await proxy.$axios.post(
        '/api/userprofile/update_avatar',
        formData,
    ).then(function ({ data }) {
        if (data.type === 'success') {
            avatarVersion.value += 1;
            user.value.left_avatar_n -= 1;
            refresh(user.value.id);
        } else if (data.type === 'error') {
            baseErrorNotification(t('local.errorTitle'), t(`local.errorMsg.${data.object}.${data.category}`));
        }
    }).catch(httpErrorNotification);
}

const i18nMessages = {
    'zh-cn': { local: {
        errorTitle: '头像更新失败',
        errorMsg: {
            avatar: {
                oversize: '头像文件过大，请上传小于300KB的文件',
                validation: '数据库拒绝接收该文件，请检查文件格式或联系管理员',
            },
            censorship: {
                unknown: '机器审核发生未知错误，请联系管理员',
                illegal: '未通过机器审核，请更换文件或联系管理员进行人工审核',
            },
        },
        tooltipBase: '点击修改头像（剩余{0}次）',
        tooltipCooldown: '头像每年可修改一次。下次可修改：',
        tooltipExpTime: '高级sub200后才可以修改头像',
        qualificationLoading: '正在检查头像修改资格',
        qualificationError: '头像修改资格查询失败，请重试',
    } },
    en: { local: {
        errorTitle: 'Avatar Update Failed',
        errorMsg: {
            avatar: {
                oversize: 'Avatar file is too large. Please upload a file smaller than 300KB',
                validation: 'File rejected by database. Please check the file format or contact a moderator',
            },
            censorship: {
                unknown: 'Unknown error occurred in censorship. Please contact a moderator',
                illegal: 'The content is blocked by censorship. Please use another file or contact a moderator for manual review',
            },
        },
        tooltipBase: 'Click to change avatar ({0} times left)',
        tooltipCooldown: 'Avatar can be changed once every year. Next available time: ',
        tooltipExpTime: 'Achieve expert sub200 to set avatar',
        qualificationLoading: 'Checking avatar eligibility',
        qualificationError: 'Could not check avatar eligibility. Please retry',
    } },
    es: { local: {
        errorTitle: 'Actualización del avatar fallida',
        errorMsg: {
            avatar: {
                oversize: 'El archivo del avatar es demasiado grande. Por favor, suba un archivo menor a 300 KB',
                validation: 'El archivo fue rechazado por la base de datos. Por favor, revise el formato del archivo o contacte a un moderador',
            },
            censorship: {
                unknown: 'Ocurrió un error desconocido en la censura. Por favor, contacte a un moderador',
                illegal: 'El contenido fue bloqueado por censura. Por favor, use otro archivo o contacte a un moderador para revisión manual',
            },
        },
        tooltipBase: 'Haga clic para cambiar el avatar ({0} veces restantes)',
        tooltipCooldown: 'El avatar puede cambiarse una vez al año. Próxima fecha disponible: ',
        tooltipExpTime: 'Logra sub200 experto para establecer el avatar',
        qualificationLoading: 'Verificando la elegibilidad del avatar',
        qualificationError: 'No se pudo verificar la elegibilidad del avatar. Por favor, intente nuevamente',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>
