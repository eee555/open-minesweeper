import { beforeEach, describe, expect, it, vi } from 'vitest';

import { confirmSaoleiBind, fetchSaoleiBindRequest, isSaoleiBindToken, SaoleiBindError } from './saoleiBindService';

const { get, post } = vi.hoisted(() => ({
    get: vi.fn<(url: string, config?: unknown) => Promise<{ data: unknown }>>(),
    post: vi.fn<(url: string, data?: unknown, config?: unknown) => Promise<{ data: unknown }>>(),
}));
vi.mock('@/http', () => ({ default: { get, post } }));

const token = 'a'.repeat(24) + 'b'.repeat(24); // 48 位 hex

const axiosError = (status: number) => {
    const error = new Error('request failed') as Error & { isAxiosError?: boolean; response?: { status: number } };
    error.isAxiosError = true;
    error.response = { status };
    return error;
};

describe('saolei bind authorization page service', () => {
    beforeEach(() => {
        vi.resetAllMocks();
    });

    it('validates the 48-hex token format', () => {
        expect(isSaoleiBindToken(token)).toBe(true);
        expect(isSaoleiBindToken('short')).toBe(false);
        expect(isSaoleiBindToken(undefined)).toBe(false);
        expect(isSaoleiBindToken(`${token}x`)).toBe(false);
    });

    it('fetches the pending request info', async () => {
        get.mockResolvedValueOnce({ data: { status: 0, uid: 2051, username: 'cphq1' } });
        await expect(fetchSaoleiBindRequest(token)).resolves.toEqual({ status: 0, uid: 2051, username: 'cphq1' });
        expect(get).toHaveBeenCalledWith('/api/accountlink/saolei/bind/request', { params: { token } });
    });

    it.each([
        [401, 'login_required'],
        [404, 'invalid_token'],
        [500, 'network'],
    ])('maps request failure status %i to %s', async (status, category) => {
        get.mockRejectedValueOnce(axiosError(status));
        await expect(fetchSaoleiBindRequest(token)).rejects.toMatchObject({ category });
    });

    it('confirms the link with the sync toggle', async () => {
        post.mockResolvedValueOnce({ data: { type: 'success' } });
        await expect(confirmSaoleiBind(token, true)).resolves.toBeUndefined();
        expect(post).toHaveBeenCalledWith('/api/accountlink/saolei/bind/confirm', { token, sync: true }, expect.anything());
    });

    it.each([
        [401, 'login_required'],
        [404, 'invalid_token'],
        [409, 'collision'],
        [0, 'network'],
    ])('maps confirm failure status %i to %s', async (status, category) => {
        post.mockRejectedValueOnce(status === 0 ? new Error('boom') : axiosError(status));
        const promise = confirmSaoleiBind(token, false);
        await expect(promise).rejects.toBeInstanceOf(SaoleiBindError);
        await expect(promise).rejects.toMatchObject({ category });
    });
});
