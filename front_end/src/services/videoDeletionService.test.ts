import { AxiosHeaders } from 'axios';
import type { AxiosResponse } from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { deleteVideosSequentially, fetchVideoDeletionAccess, parseVideoDeletionIds } from './videoDeletionService';
import type { VideoDeletionResult } from './videoDeletionService';

import $axios from '@/http';

describe('video deletion input', () => {
    it('accepts pasted IDs or a JSON array and deduplicates in input order', () => {
        expect(parseVideoDeletionIds(' 3, 1\n3，2; 4； ')).toEqual([3, 1, 2, 4]);
        expect(parseVideoDeletionIds('[3, 1, 3, 2]')).toEqual([3, 1, 2]);
        expect(parseVideoDeletionIds('')).toEqual([]);
    });

    it.each(['1, x', '1,0', '1,-2', '1,1.5', '1,1e2', '1,0x10', '[1,"2"]', '[1,true]', '[1,null]', '[1,2.5]', '[1,', '9007199254740992'])('rejects the entire input %s', (input) => {
        expect(() => parseVideoDeletionIds(input)).toThrow();
    });
});

describe('sequential single-video deletion', () => {
    const originalAdapter = $axios.defaults.adapter;
    afterEach(() => {
        $axios.defaults.adapter = originalAdapter;
    });

    it('checks superuser access and obtains a CSRF token without deleting', async () => {
        $axios.defaults.adapter = (config) => {
            expect(config.url).toBe('/api/video/admin/delete');
            expect(config.method).toBe('get');
            return Promise.resolve({ data: { csrf_token: 'token' }, status: 200, statusText: 'OK', headers: new AxiosHeaders(), config });
        };
        await expect(fetchVideoDeletionAccess()).resolves.toBe('token');
    });

    it('awaits each response and sends one JSON ID plus CSRF token per request', async () => {
        const requests: number[] = [];
        const results: VideoDeletionResult[] = [];
        let release: (() => void) | undefined;
        $axios.defaults.adapter = (config) => {
            const body = JSON.parse(String(config.data)) as { id: number };
            expect(config.url).toBe('/api/video/admin/delete');
            expect(config.headers.getContentType()).toBe('application/json');
            expect(config.headers.get('X-CSRFToken')).toBe('token');
            expect(Object.keys(body)).toEqual(['id']);
            requests.push(body.id);
            const response = { data: { id: body.id, deleted: body.id !== 11, affected_tournament_ids: [] }, status: 200, statusText: 'OK', headers: new AxiosHeaders(), config };
            if (body.id === 11) return new Promise<AxiosResponse<VideoDeletionResult>>((resolve) => {
                release = () => {
                    resolve(response);
                };
            });
            return Promise.resolve(response);
        };
        const operation = deleteVideosSequentially([11, 22], 'token', (result) => {
            results.push(result);
        }, () => false);
        await vi.waitFor(() => {
            expect(requests).toEqual([11]);
        });
        expect(results).toEqual([]);
        release?.();
        await operation;
        expect(requests).toEqual([11, 22]);
        expect(results.map((result) => [result.id, result.deleted])).toEqual([[11, false], [22, true]]);
    });

    it('stops on an uncertain failure and preserves prior confirmed results without retrying', async () => {
        const requests: number[] = [];
        const results: VideoDeletionResult[] = [];
        $axios.defaults.adapter = (config) => {
            const { id } = JSON.parse(String(config.data)) as { id: number };
            requests.push(id);
            if (id === 22) return Promise.reject(new Error('timeout'));
            return Promise.resolve({ data: { id, deleted: true, affected_tournament_ids: [] }, status: 200, statusText: 'OK', headers: new AxiosHeaders(), config });
        };
        await expect(deleteVideosSequentially([11, 22, 33], 'token', (result) => {
            results.push(result);
        }, () => false)).rejects.toThrow('timeout');
        expect(requests).toEqual([11, 22]);
        expect(results.map((result) => result.id)).toEqual([11]);
    });

    it('finishes the in-flight request but sends no later request when stopped or unmounted', async () => {
        const requests: number[] = [];
        const results: VideoDeletionResult[] = [];
        let stopped = false;
        let release: (() => void) | undefined;
        $axios.defaults.adapter = (config) => {
            const { id } = JSON.parse(String(config.data)) as { id: number };
            requests.push(id);
            return new Promise<AxiosResponse<VideoDeletionResult>>((resolve) => {
                release = () => {
                    resolve({ data: { id, deleted: true, affected_tournament_ids: [] }, status: 200, statusText: 'OK', headers: new AxiosHeaders(), config });
                };
            });
        };
        const operation = deleteVideosSequentially([11, 22], 'token', (result) => {
            results.push(result);
        }, () => stopped);
        await vi.waitFor(() => {
            expect(requests).toEqual([11]);
        });
        stopped = true;
        release?.();
        await operation;
        expect(requests).toEqual([11]);
        expect(results.map((result) => result.id)).toEqual([11]);
    });
});
