import type { AxiosInstance } from 'axios';

import { store } from '@/store';
import type { UserProfileData } from '@/utils/userprofile';

const csrfReady = new WeakMap<AxiosInstance, Promise<void>>();
let loginVersion = 0;

export function applySelfAccess(userId: number, revision: number, access: Pick<UserProfileData, 'verified' | 'can_submit_replays'>): boolean {
    // 只原地更新后端派生的准入字段，保留 store.user 的对象身份；替换整个对象会让个人设置页被重新加载并丢失保存结果。
    if (userId <= 0 || store.user.id !== userId || revision !== store.sessionRevision) return false;
    store.user.verified = access.verified ?? false;
    store.user.can_submit_replays = access.can_submit_replays ?? false;
    return true;
}

export async function refreshSelfAccess(userId: number, client: AxiosInstance): Promise<boolean> {
    if (userId <= 0 || store.user.id !== userId) return false;
    const revision = store.sessionRevision;
    const { data } = await client.get<{ user: UserProfileData | null }>('/api/common/loginauto', { params: { _t: Date.now() } });
    // 期间若已切换到其他账号，不能把这个页面的刷新结果写回登录态。
    if (data.user?.id !== userId) return false;
    return applySelfAccess(userId, revision, data.user);
}

export async function applyLoginSession(user: UserProfileData, client: AxiosInstance): Promise<boolean> {
    const version = ++loginVersion;
    const revision = store.sessionRevision;
    if (user.is_staff === true || user.is_superuser === true) {
        let ready = csrfReady.get(client);
        if (!ready) {
            ready = import('./adminCsrf').then(({ installAdminCsrfInterceptor }) => {
                installAdminCsrfInterceptor(client, () => store.user.is_staff || store.user.is_superuser);
            }).catch((error: unknown) => {
                csrfReady.delete(client);
                throw error;
            });
            csrfReady.set(client, ready);
        }
        await ready;
    }
    if (version !== loginVersion || revision !== store.sessionRevision) return false;
    store.login(user);
    return true;
}
