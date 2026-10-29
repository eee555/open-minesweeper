<template>
    <div :class="{ 'horizontal-profile': direction === 'horizontal', 'vertical-profile': direction === 'vertical' }">
        <div class="profile">
            <div class="avatar">
                <Avatar v-model:user="store.player" :is-self="user.id === store.user.id" :exp-time-ms="store.expTimeMs" :qualification-status="store.qualificationStatus" />
            </div>
            <div v-if="user.isNameHidden" class="realname" data-cy="hidden-profile-name">
                {{ t('local.hiddenName', { id: user.id }) }}
            </div>
            <template v-else>
                <div>
                    <span class="username">
                        {{ user.username }}
                    </span>
                    <span class="id">
                        #{{ user.id }}
                    </span>
                </div>
                <div class="realname">
                    {{ user.isAnonymous ? t('anonymous') : user.realname }}
                </div>
                <div class="fullname">
                    {{ formatName(user.firstname, user.lastname, local.nameFormat) }}
                </div>
            </template>
        </div>
        <MemorialBadge v-if="user.is_memorial" />
        <RouterLink v-if="user.is_memorial && store.user.is_superuser" :to="{ path: '/superuser/memorial', query: { id: user.id } }" class="link">
            {{ t('local.uploadMemorial') }}
        </RouterLink>
        <ProfilePins class="profile-pins" :user-id="user.id" />
        <BaseButton v-if="store.isSelf" class="edit-button" @click="router.push({ name: 'user-settings', params: { id: user.id } })">
            {{ t('local.editButton') }}
        </BaseButton>
        <ProfileQualification v-if="store.isSelf" />
        <div class="signature">
            {{ user.signature }}
        </div>
    </div>
</template>

<script setup lang="ts">
import type { PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { RouterLink, useRouter } from 'vue-router';

import Avatar from './Avatar.vue';
import ProfilePins from './ProfilePins.vue';
import ProfileQualification from './ProfileQualification.vue';

import BaseButton from '@/components/common/BaseButton.vue';
import MemorialBadge from '@/components/widgets/MemorialBadge.vue';
import { local, store } from '@/store';
import { formatName } from '@/utils/strings';
import { UserProfile } from '@/utils/userprofile';

defineProps({
    user: {
        type: UserProfile,
        default: () => new UserProfile(),
    },
    direction: {
        type: String as PropType<'horizontal' | 'vertical'>,
        default: 'vertical',
    },
});

const router = useRouter();

const i18nMessages = {
    'zh-cn': { local: {
        editButton: '编辑信息',
        hiddenName: '用户 #{id}',
        uploadMemorial: '补传纪念录像',
    } },
    en: { local: {
        editButton: 'Edit Profile',
        hiddenName: 'User #{id}',
        uploadMemorial: 'Upload memorial replays',
    } },
};

const { t } = useI18n({ messages: i18nMessages });
</script>

<style scoped lang="less">
.profile-pins {
    width: 100%;
}

/* 横向布局：窄屏顶部栏 */
.horizontal-profile {
    display: flex;
    flex-wrap: wrap;
    row-gap: 0.5rem;
    align-items: center;
    justify-content: space-between;
    background-color: var(--ui-bg-color);
    border-bottom: 1px solid var(--ui-border-color-light);
    box-sizing: border-box;

    .profile {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-shrink: 0;
    }

    .avatar {
        height: 64px;
        aspect-ratio: 1 / 1;
        overflow: hidden;
        flex-shrink: 0;
    }

    .username {
        font-weight: 600;
        font-size: var(--ui-font-size-extra-large);
        color: var(--ui-text-color-primary);
    }

    .id {
        font-size: var(--ui-font-size-large);
        color: var(--ui-text-color-secondary);
    }

    .realname {
        font-weight: 500;
        font-size: var(--ui-font-size-large);
        color: var(--ui-text-color-primary);
    }
    .fullname {
        font-size: var(--ui-font-size-small);
        color: var(--ui-text-color-regular);
    }

    .signature {
        width: 100%;
        max-height: 64px;
        overflow: auto;
        font-size: var(--ui-font-size-extra-small);
        color: var(--ui-text-color-placeholder);
        padding-left: 12px;
        white-space: pre-wrap;
    }

    .edit-button {
        margin-left: auto;
    }
}

/* 纵向布局：宽屏侧边栏 */
.vertical-profile {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
    height: 100%;
    padding: 12px 8px;
    background-color: var(--ui-bg-color);
    border-right: 1px solid var(--ui-border-color-light);
    box-sizing: border-box;

    .profile {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        margin-bottom: 16px;
    }

    .avatar {
        width: 100%;
        aspect-ratio: 1 / 1;
        overflow: hidden;
        margin-bottom: 8px;
    }

    .username {
        font-size: 18px;
        font-weight: 600;
        color: var(--ui-text-color-primary);
        text-align: center;
    }

    .id {
        font-size: 13px;
        color: var(--ui-text-color-secondary);
        text-align: center;
    }

    .realname {
        font-weight: 500;
        font-size: var(--ui-font-size-large);
        color: var(--ui-text-color-regular);
        text-align: center;
    }
    .fullname {
        font-size: var(--ui-font-size-small);
        color: var(--ui-text-color-regular);
        text-align: center;
    }

    .signature {
        width: 100%;
        font-size: var(--ui-font-size-extra-small);
        line-height: 1.6;
        color: var(--ui-text-color-placeholder);
        overflow: auto;
        word-break: break-word;
        white-space: pre-wrap;
    }

    .edit-button {
        width: 100%;
        margin-top: 1rem;
        order: 1;
    }
}
</style>
