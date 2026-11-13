import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { UserProfile } from './userprofile';

describe('UserProfile', () => {
    const fixedNow = new Date('2025-06-15T12:00:00Z');

    beforeEach(() => {
        vi.useFakeTimers();
        vi.setSystemTime(fixedNow);
    });

    afterEach(() => {
        vi.useRealTimers();
    });

    describe('constructor', () => {
        it('Empty initialization', () => {
            const profile = new UserProfile();

            expect(profile.id).toBe(0);
            expect(profile.username).toBe('');
            expect(profile.realname).toBe('');
            expect(profile.firstname).toBe('');
            expect(profile.lastname).toBe('');
            expect(profile.is_banned).toBe(false);
            expect(profile.is_staff).toBe(false);
            expect(profile.country).toBe('');
            expect(profile.signature).toBe('');
            expect(profile.last_change_avatar).toEqual(fixedNow);
            expect(profile.last_change_signature).toEqual(fixedNow);
            expect(profile.left_avatar_n).toBe(0);
            expect(profile.left_signature_n).toBe(0);
            expect(profile.accountlink).toEqual([]);
            expect(profile.identifiers).toBeUndefined();
            expect(profile.videos).toBeUndefined();
        });

        it('Complete initialization', () => {
            const data = {
                id: 42,
                username: 'john_doe',
                realname: 'John Doe',
                firstname: 'John',
                lastname: 'Doe',
                is_banned: true,
                is_staff: true,
                country: 'US',
                signature: 'Hello World',
                last_change_avatar: '2023-01-01T00:00:00Z',
                last_change_signature: '2023-06-01T00:00:00Z',
                left_avatar_n: 3,
                left_signature_n: 5,
                identifiers: ['id1', 'id2'],
            };

            const profile = new UserProfile(data);

            expect(profile.id).toBe(42);
            expect(profile.username).toBe('john_doe');
            expect(profile.realname).toBe('John Doe');
            expect(profile.firstname).toBe('John');
            expect(profile.lastname).toBe('Doe');
            expect(profile.is_banned).toBe(true);
            expect(profile.is_staff).toBe(true);
            expect(profile.country).toBe('US');
            expect(profile.signature).toBe('Hello World');
            expect(profile.last_change_avatar).toEqual(new Date('2023-01-01T00:00:00Z'));
            expect(profile.last_change_signature).toEqual(new Date('2023-06-01T00:00:00Z'));
            expect(profile.left_avatar_n).toBe(3);
            expect(profile.left_signature_n).toBe(5);
            expect(profile.identifiers).toEqual(['id1', 'id2']);
        });

        it('Partial initialization', () => {
            const data = { id: 10, username: 'test' };
            const profile = new UserProfile(data);

            expect(profile.id).toBe(10);
            expect(profile.username).toBe('test');
            expect(profile.realname).toBe('');
            expect(profile.firstname).toBe('');
        });

        it('Realname being anonymous', () => {
            const data = { realname: '匿名' };
            const profile = new UserProfile(data);

            expect(profile.realname).toBe('');
        });
    });

    describe('getter: isAnonymous', () => {
        it.each(['', '   ', '匿名'])('treats %j as missing without a response status field', (realname) => {
            expect(new UserProfile({ realname }).isAnonymous).toBe(true);
        });

        it.each(['realname', 'firstname', 'lastname'])('recognizes the hidden marker in %s without treating it as an international name', (field) => {
            const profile = new UserProfile({ realname: 'Original', firstname: 'Given', lastname: 'Family', [field]: 'hidden' });
            expect(profile.isAnonymous).toBe(false);
            expect(profile.isNameHidden).toBe(true);
            expect(profile.hasInternationalName).toBe(false);
            expect(profile.canSetName).toBe(false);
        });

        it('hides an owner profile while preserving original names and editability', () => {
            const profile = new UserProfile({ realname: 'Original', can_hide_realname: true, hide_realname: true });
            expect(profile.isNameHidden).toBe(true);
            expect(profile.realname).toBe('Original');
            expect(profile.canSetName).toBe(true);
            profile.can_hide_realname = false;
            expect(profile.isNameHidden).toBe(false);
            profile.can_hide_realname = true;
            profile.realname = '';
            expect(profile.isNameHidden).toBe(false);
        });
        it('false', () => {
            const profile = new UserProfile({ realname: 'Alice' });
            expect(profile.isAnonymous).toBe(false);
        });
    });

    describe('getter: canSubmitReplays', () => {
        it.each(['', '   ', '匿名'])('requires verification when the real name is %j', (realname) => {
            const profile = new UserProfile({ id: 42, realname });
            expect(profile.canSubmitReplays).toBe(false);
            profile.verified = true;
            expect(profile.canSubmitReplays).toBe(true);
        });

        it.each(['Alice', 'hidden'])('accepts the existing real name representation %j', (realname) => {
            expect(new UserProfile({ id: 42, realname }).canSubmitReplays).toBe(true);
        });

        it('does not grant access to guests or through a management role', () => {
            expect(new UserProfile({ realname: 'Alice', verified: true }).canSubmitReplays).toBe(false);
            expect(new UserProfile({ id: 42, is_staff: true, is_superuser: true }).canSubmitReplays).toBe(false);
        });

        it('updates access immediately when the real name or verification changes', () => {
            const profile = new UserProfile({ id: 42 });
            expect(profile.canSubmitReplays).toBe(false);
            profile.realname = 'Alice';
            expect(profile.canSubmitReplays).toBe(true);
            profile.realname = '';
            expect(profile.canSubmitReplays).toBe(false);
            profile.verified = true;
            expect(profile.canSubmitReplays).toBe(true);
            profile.verified = false;
            expect(profile.canSubmitReplays).toBe(false);
        });
    });

    describe('getter: canSetName', () => {
        it('realname not set', () => {
            const profile = new UserProfile({ firstname: 'a', lastname: 'b' });
            expect(profile.canSetName).toBe(true);
        });

        it('firstname not set', () => {
            const profile = new UserProfile({ realname: 'a', lastname: 'b' });
            expect(profile.canSetName).toBe(true);
        });

        it('lastname not set', () => {
            const profile = new UserProfile({ realname: 'a', firstname: 'b' });
            expect(profile.canSetName).toBe(true);
        });

        it('All set', () => {
            const profile = new UserProfile({ realname: 'a', firstname: 'b', lastname: 'c' });
            expect(profile.canSetName).toBe(false);
        });
    });

    describe('getter: hasInternationalName', () => {
        it('None set', () => {
            const profile = new UserProfile();
            expect(profile.hasInternationalName).toBe(false);
        });

        it('firstname not set', () => {
            const profile = new UserProfile({ lastname: 'a' });
            expect(profile.hasInternationalName).toBe(false);
        });

        it('lastname not set', () => {
            const profile = new UserProfile({ firstname: 'a' });
            expect(profile.hasInternationalName).toBe(false);
        });

        it('All set', () => {
            const profile = new UserProfile({ firstname: 'a', lastname: 'b' });
            expect(profile.hasInternationalName).toBe(true);
        });
    });

    describe('getter: nextAvatarAvailable', () => {
        it('left_avatar_n > 0', () => {
            const lastChange = new Date('2023-05-01T00:00:00Z');
            const profile = new UserProfile({
                left_avatar_n: 1,
                last_change_avatar: lastChange.toISOString(),
            });
            expect(profile.nextAvatarAvailable).toEqual(lastChange);
        });

        it('left_avatar_n == 0', () => {
            const lastChange = new Date('2023-05-01T00:00:00Z');
            const profile = new UserProfile({
                left_avatar_n: 0,
                last_change_avatar: lastChange.toISOString(),
            });
            const expected = new Date(Date.UTC(2024, 0, 1, 0, 0, 0));
            expect(profile.nextAvatarAvailable).toEqual(expected);
        });
    });

    describe('getter: nextSignatureAvailable', () => {
        it('left_signature_n > 0', () => {
            const lastSigChange = new Date('2023-03-15T00:00:00Z');
            const profile = new UserProfile({
                left_signature_n: 1,
                last_change_signature: lastSigChange.toISOString(),
            });
            expect(profile.nextSignatureAvailable).toEqual(lastSigChange);
        });

        it('left_signature_n == 0', () => {
            const lastSigChange = new Date('2023-05-01T00:00:00Z');
            const profile = new UserProfile({
                left_signature_n: 0,
                last_change_signature: lastSigChange.toISOString(),
            });
            // 下一次应为 2023-06-01T00:00:00Z
            const expected = new Date(Date.UTC(2023, 5, 1, 0, 0, 0));
            expect(profile.nextSignatureAvailable).toEqual(expected);
        });
    });

    describe('newAvatarBudget', () => {
        it('Different years', () => {
            const lastChange = new Date('2022-03-10T00:00:00Z');
            const profile = new UserProfile({
                left_avatar_n: 2,
                last_change_avatar: lastChange.toISOString(),
            });
            const newDate = new Date('2025-06-15T00:00:00Z');
            // 公式: left_avatar_n + (newDateYear - lastChangeYear) = 2 + (2025 - 2022) = 5
            expect(profile.newAvatarBudget(newDate)).toBe(5);
        });

        it('Same year', () => {
            const lastChange = new Date('2025-01-01T00:00:00Z');
            const profile = new UserProfile({
                left_avatar_n: 3,
                last_change_avatar: lastChange.toISOString(),
            });
            const newDate = new Date('2025-12-31T00:00:00Z');
            expect(profile.newAvatarBudget(newDate)).toBe(3);
        });
    });

    describe('newSignatureBudget', () => {
        it('Normal', () => {
            const lastSigChange = new Date('2023-01-15T00:00:00Z');
            const profile = new UserProfile({
                left_signature_n: 4,
                last_change_signature: lastSigChange.toISOString(),
            });
            const newDate = new Date('2024-03-10T00:00:00Z');
            expect(profile.newSignatureBudget(newDate)).toBe(18);
        });
    });
});
