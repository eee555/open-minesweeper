import type { AxiosInstance } from 'axios';

import { store } from '@/store';
import type { UserProfileData } from '@/utils/userprofile';

const csrfReady = new WeakMap<AxiosInstance, Promise<void>>();
let loginVersion = 0;

export function applySelfVerification(userId: number, revision: number, verified: boolean): boolean {
    // 原地同步认证，准入由 UserProfile getter 计算；保留对象身份以免个人设置页丢失保存结果。
    if (userId <= 0 || store.user.id !== userId || revision !== store.sessionRevision) return false;
    store.user.verified = verified;
    return true;
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
