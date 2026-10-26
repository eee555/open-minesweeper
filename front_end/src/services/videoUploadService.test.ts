import { AxiosError, AxiosHeaders } from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { normalizeVideoUploadResponse, uploadVideoFile } from './videoUploadService';

import $axios from '@/http';
import { MS_State } from '@/utils/ms_const';

const { syncAfterUpload } = vi.hoisted(() => ({ syncAfterUpload: vi.fn() }));
vi.mock('./medalService', () => ({ syncMedalsAfterUpload: syncAfterUpload }));

describe('uploadVideoFile', () => {
    afterEach(() => {
        vi.restoreAllMocks();
        syncAfterUpload.mockClear();
    });

    it('starts medal synchronization only for a successful upload', async () => {
        vi.spyOn($axios, 'post').mockResolvedValueOnce({ data: { type: 'success', data: { id: 42, state: MS_State.Official } } }).
            mockResolvedValueOnce({ data: { type: 'error', object: 'file' } });
        await expect(uploadVideoFile(new File(['video'], 'video.avf'))).resolves.toEqual({ type: 'success', id: 42, state: MS_State.Official });
        expect(syncAfterUpload).toHaveBeenCalledTimes(1);
        await uploadVideoFile(new File(['video'], 'duplicate.avf'));
        expect(syncAfterUpload).toHaveBeenCalledTimes(1);
    });

    it.each([402, 403, 500])('handles HTTP %i with an empty response body', async (status) => {
        const error = new AxiosError('Upload rejected', AxiosError.ERR_BAD_RESPONSE, undefined, undefined, {
            status,
            statusText: '',
            data: '',
            headers: {},
            config: { headers: new AxiosHeaders() },
        });
        vi.spyOn($axios, 'post').mockRejectedValue(error);

        const result = uploadVideoFile(new File(['video'], 'video.avf'));
        if (status === 402) {
            await expect(result).resolves.toEqual({ type: 'error', status: 'quota' });
        } else {
            await expect(result).rejects.toBe(error);
        }
    });

    it('preserves network errors without a response', async () => {
        const error = new AxiosError('Network Error', AxiosError.ERR_NETWORK);
        vi.spyOn($axios, 'post').mockRejectedValue(error);

        await expect(uploadVideoFile(new File(['video'], 'video.avf'))).rejects.toBe(error);
    });
});

describe('normalizeVideoUploadResponse', () => {
    it('maps incomplete replay errors to the incomplete status', () => {
        expect(normalizeVideoUploadResponse({ type: 'error', object: 'file', category: 'incomplete' })).toEqual({ type: 'error', status: 'incomplete' });
    });

    it('maps successful upload response to uploaded video data', () => {
        expect(normalizeVideoUploadResponse({
            type: 'success',
            object: 'videomodel',
            category: 'upload',
            data: {
                id: 42,
                state: MS_State.Official,
            },
        })).toEqual({
            type: 'success',
            id: 42,
            state: MS_State.Official,
        });
    });

    it('maps file errors to upload collision status', () => {
        expect(normalizeVideoUploadResponse({
            type: 'error',
            object: 'file',
        })).toEqual({
            type: 'error',
            status: 'collision',
        });
    });

    it('maps identifier errors to censorship status', () => {
        expect(normalizeVideoUploadResponse({
            type: 'error',
            object: 'identifier',
        })).toEqual({
            type: 'error',
            status: 'censorship',
        });
    });

    it('falls back to generic upload failure for other error responses', () => {
        expect(normalizeVideoUploadResponse({
            type: 'error',
            obj: 'userprofile',
            category: 'realname_required',
        })).toEqual({
            type: 'error',
            status: 'upload',
        });
    });
});
