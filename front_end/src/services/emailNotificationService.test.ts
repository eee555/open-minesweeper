import { AxiosHeaders } from 'axios';
import { afterEach, describe, expect, it } from 'vitest';

import { saveEmailNotifications } from './emailNotificationService';

import $axios from '@/http';

describe('email notification settings transport', () => {
    const originalAdapter = $axios.defaults.adapter;
    afterEach(() => {
        $axios.defaults.adapter = originalAdapter;
    });

    it('sends JSON with boolean changes despite the site-wide form default', async () => {
        const changes = [
            { type: 'staff_video_plain', enabled: true },
            { type: 'staff_media_review', enabled: false },
        ] as const;
        const mask = 2 ** 31 + 4;
        const settings = { email_notification_mask: mask, language: 'es' } as const;
        const originalContentType = $axios.defaults.headers['Content-Type'];
        $axios.defaults.adapter = (config) => {
            expect(config.url).toBe('/api/userprofile/email-notifications');
            expect(config.method).toBe('patch');
            expect(config.headers.getContentType()).toBe('application/json');
            const body: unknown = JSON.parse(String(config.data));
            expect(body).toEqual({ changes, language: 'es' });
            return Promise.resolve({ data: settings, status: 200, statusText: 'OK', headers: new AxiosHeaders(), config });
        };
        await expect(saveEmailNotifications({ changes: [...changes], language: 'es' })).resolves.toEqual(settings);
        expect($axios.defaults.headers['Content-Type']).toBe(originalContentType);
    });

    it('can save only the language without submitting subscription bits', async () => {
        const settings = { email_notification_mask: 2 ** 31 + 16, language: 'zh-cn' } as const;
        $axios.defaults.adapter = (config) => {
            const body: unknown = JSON.parse(String(config.data));
            expect(body).toEqual({ language: 'zh-cn' });
            return Promise.resolve({ data: settings, status: 200, statusText: 'OK', headers: new AxiosHeaders(), config });
        };
        await expect(saveEmailNotifications({ language: 'zh-cn' })).resolves.toEqual(settings);
    });
});
