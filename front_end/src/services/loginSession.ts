import type { AxiosInstance } from 'axios';

import { store } from '@/store';
import type { UserProfileData } from '@/utils/userprofile';

const csrfReady = new WeakMap<AxiosInstance, Promise<void>>();
let loginVersion = 0;

export async function refreshSelfSession(userId: number, client: AxiosInstance): Promise<boolean> {
    if (userId <= 0 || store.user.id !== userId) return false;
    const { data } = await client.get<{ user: UserProfileData | null }>('/api/common/loginauto', { params: { _t: Date.now() } });
    // 期间若已切换到其他账号，不能把这个页面的刷新结果写回登录态。
    if (data.user?.id !== userId || store.user.id !== userId) return false;
    return applyLoginSession(data.user, client);
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
