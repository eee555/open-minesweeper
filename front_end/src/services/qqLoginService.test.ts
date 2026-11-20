import { afterEach, describe, expect, it, vi } from 'vitest';

import { bindQQRecoveryEmail, cancelQQLogin, fetchQQLoginStatus, qqLoginErrorKey, registerQQAccount, startQQLogin, unlinkQQLogin } from './qqLoginService';

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('@/http', () => ({ default: { get, post } }));
afterEach(() => {
    vi.resetAllMocks();
});

describe('QQ login API', () => {
    it('requests server-side authorization with an explicit intent and validates its destination', async () => {
        const url = 'https://graph.qq.com/oauth2.0/authorize?client_id=12345&state=test';
        post.mockResolvedValue({ data: { authorization_url: url } });
        expect(await startQQLogin()).toBe(url);
        expect(post).toHaveBeenLastCalledWith('/api/userprofile/qq/start', { mode: 'login' }, expect.any(Object));
        await startQQLogin('bind');
        expect(post).toHaveBeenLastCalledWith('/api/userprofile/qq/start', { mode: 'bind' }, expect.any(Object));
        for (const invalid of ['https://evil.test/oauth2.0/authorize', 'http://graph.qq.com/oauth2.0/authorize', 'https://graph.qq.com/token', 'https://user@graph.qq.com/oauth2.0/authorize']) {
            post.mockResolvedValueOnce({ data: { authorization_url: invalid } });
            await expect(startQQLogin()).rejects.toThrow();
        }
    });

    it('keeps confirmation, cancellation, unlinking and verified email submission separate', async () => {
        post.mockResolvedValue({ data: { user: { id: 7 } } });
        get.mockResolvedValue({ data: { pending: { nickname: 'QQ Player' } } });
        expect(await fetchQQLoginStatus()).toEqual({ pending: { nickname: 'QQ Player' } });
        expect(await registerQQAccount()).toEqual({ id: 7 });
        await cancelQQLogin();
        await unlinkQQLogin();
        await bindQQRecoveryEmail('person@example.com', 'key', '123456');
        expect(post).toHaveBeenCalledWith('/api/userprofile/qq/register');
        expect(post).toHaveBeenCalledWith('/api/userprofile/qq/cancel');
        expect(post).toHaveBeenCalledWith('/api/userprofile/qq/unlink');
        expect(post).toHaveBeenCalledWith('/api/userprofile/qq/recovery-email', { email: 'person@example.com', email_key: 'key', email_captcha: '123456' }, expect.any(Object));
    });

    it('maps only known error categories to messages', () => {
        expect(qqLoginErrorKey('expired')).toBe('qqLogin.errors.expired');
        expect(qqLoginErrorKey('arbitrary.key')).toBe('qqLogin.errors.remote_failed');
        expect(qqLoginErrorKey({ isAxiosError: true, response: { status: 503, data: { category: 'not_configured' } } })).toBe('qqLogin.errors.not_configured');
        expect(qqLoginErrorKey({ isAxiosError: true, response: { status: 429 } })).toBe('qqLogin.errors.rate_limited');
        expect(qqLoginErrorKey({ isAxiosError: true, response: { status: 502, data: null } })).toBe('qqLogin.errors.remote_failed');
    });
});
