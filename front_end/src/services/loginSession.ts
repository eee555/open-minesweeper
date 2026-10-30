import type { AxiosInstance } from 'axios';

import { store } from '@/store';
import type { UserProfileData } from '@/utils/userprofile';

const csrfReady = new WeakMap<AxiosInstance, Promise<void>>();
let loginVersion = 0;

export async function applyLoginSession(user: UserProfileData, client: AxiosInstance): Promise<boolean> {
    const version = ++loginVersion;
    const revision = store.sessionRevision;
    if (user.is_staff || user.is_superuser) {
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
