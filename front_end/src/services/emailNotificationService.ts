import $axios from '@/http';
import type { UserLanguage } from '@/utils/userprofile';

export const emailNotificationTypes = [
    { type: 'staff_media_review', flag: 1 },
    { type: 'staff_video_frozen', flag: 2 },
    { type: 'staff_video_plain', flag: 4 },
    { type: 'staff_account_link_review', flag: 8 },
    { type: 'staff_identifier_unsafe', flag: 16 },
] as const;

export type EmailNotificationType = typeof emailNotificationTypes[number]['type'];
export interface EmailNotificationChange {
    type: EmailNotificationType;
    enabled: boolean;
}

export interface EmailNotificationChanges {
    changes?: EmailNotificationChange[];
    language?: UserLanguage;
}

export interface EmailNotificationSettings {
    email_notification_mask: number;
    language: UserLanguage;
}

export async function saveEmailNotifications(settings: EmailNotificationChanges): Promise<EmailNotificationSettings> {
    const { data } = await $axios.patch<EmailNotificationSettings>('/api/userprofile/email-notifications', settings, { headers: { 'Content-Type': 'application/json' } });
    return data;
}
