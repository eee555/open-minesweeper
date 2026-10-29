import { beforeEach, describe, expect, it, vi } from 'vitest';

import { planMemorialUploads, uploadMemorialBatch } from './memorialService';
import type { MemorialBinding, MemorialReplay } from './memorialService';

const { post } = vi.hoisted(() => ({ post: vi.fn() }));
vi.mock('@/http', () => ({ default: { post } }));

function replay(index: number, identifier: string): MemorialReplay {
    return { index, identifier, file: new File(['record'], `${index}.evf`), endTime: new Date(`2008-08-08T12:0${index}:00Z`), timems: 1234 };
}

describe('memorial replay import', () => {
    const anchor = new Date('2008-08-08T13:00:00Z');
    beforeEach(() => post.mockReset());

    it('uploads only explicitly selected identifiers, including an explicitly selected empty identifier', () => {
        const files = [replay(0, ''), replay(1, 'selected'), replay(2, 'other')];
        expect(planMemorialUploads(files, [], anchor)).toEqual([]);
        const uploads = planMemorialUploads(files, ['', 'selected'], anchor);
        expect(uploads.map((entry) => entry.identifier)).toEqual(['', 'selected']);
    });

    it('submits all identifiers with the first file and continues when every binding fails', async () => {
        const bindings: MemorialBinding[] = [];
        const uploads = planMemorialUploads([replay(0, 'conflict'), replay(1, 'failed'), replay(2, 'conflict')], ['conflict', 'failed'], anchor);
        post.mockResolvedValueOnce({ data: { video: { id: 9 }, bindings: [{ identifier: 'conflict', bound: false }, { identifier: 'failed', bound: false, error: 'binding failed' }] } });
        post.mockResolvedValue({ data: { video: { id: 10 }, bindings: [] } });
        await uploadMemorialBatch(42, ['conflict', 'failed', 'conflict'], bindings, uploads, 'csrf');
        expect(post).toHaveBeenCalledTimes(3);
        expect(post.mock.calls.every(([url]) => String(url).endsWith('/videos'))).toBe(true);
        expect((post.mock.calls[0][1] as FormData).get('identifiers')).toBe('["conflict","failed"]');
        expect((post.mock.calls[1][1] as FormData).get('identifiers')).toBe('[]');
        expect(bindings.map((binding) => binding.bound)).toEqual([false, false]);
        expect(uploads.every((entry) => entry.result)).toBe(true);
        expect(post.mock.calls[0][2]).toEqual({ headers: { 'X-CSRFToken': 'csrf' } });
    });

    it('keeps successful bindings after upload failure and retries only failed files with the same dates', async () => {
        const bindings: MemorialBinding[] = [];
        const uploads = planMemorialUploads([replay(0, 'selected'), replay(1, 'selected')], ['selected'], anchor);
        const failure = Object.assign(new Error('upload failed'), { isAxiosError: true, response: { status: 400, data: { category: 'invalid', bindings: [{ identifier: 'selected', bound: true }] } } });
        post.mockRejectedValueOnce(failure);
        post.mockResolvedValueOnce({ data: { video: { id: 2 }, bindings: [] } });
        await uploadMemorialBatch(42, ['selected'], bindings, uploads, 'csrf');
        expect(uploads[0].error).toBeDefined();
        expect(bindings[0].bound).toBe(true);
        expect(uploads[1].result?.id).toBe(2);
        const assignedTime = uploads[0].uploadTime.toISOString();
        post.mockResolvedValueOnce({ data: { video: { id: 1 }, bindings: [] } });
        await uploadMemorialBatch(42, ['selected'], bindings, uploads, 'csrf');
        expect(post).toHaveBeenCalledTimes(3);
        expect((post.mock.calls[2][1] as FormData).get('upload_time')).toBe(assignedTime);
        expect((post.mock.calls[2][1] as FormData).get('identifiers')).toBe('[]');
        expect(uploads[0].error).toBeUndefined();
    });

    it('retries identifier preparation when a network failure leaves its result unknown', async () => {
        const uploads = planMemorialUploads([replay(0, 'selected'), replay(1, 'selected')], ['selected'], anchor);
        post.mockRejectedValueOnce(new Error('network failure'));
        post.mockResolvedValueOnce({ data: { video: { id: 2 }, bindings: [{ identifier: 'selected', bound: true }] } });
        await uploadMemorialBatch(42, ['selected'], [], uploads, 'csrf');
        expect((post.mock.calls[1][1] as FormData).get('identifiers')).toBe('["selected"]');
    });

    it('does not submit a new request after stopping', async () => {
        const uploads = planMemorialUploads([replay(0, 'selected')], ['selected'], anchor);
        await uploadMemorialBatch(42, ['selected'], [], uploads, 'csrf', () => true);
        expect(post).not.toHaveBeenCalled();
    });
});
