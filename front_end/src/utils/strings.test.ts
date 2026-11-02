import { describe, expect, it } from 'vitest';

import {
    countRows,
    formatBytes,
    formatName,
    formatNumberSmart,
    getFileExtension,
    getSoftwareExtension,
    stringifyWithLineWrap,
} from './strings';

describe('strings', () => {
    describe('stringifyWithLineWrap', () => {
        it('Keeps short arrays on one line', () => {
            expect(stringifyWithLineWrap({ values: [1, 2, 3] }, 80, 2)).toBe(`{
  "values": [1, 2, 3]
}`);
        });

        it('Wraps arrays that exceed max line length', () => {
            expect(stringifyWithLineWrap({ values: ['alpha', 'beta', 'gamma'] }, 16, 2)).toBe(`{
  "values": ["alpha", "beta",
    "gamma"]
}`);
        });

        it('Keeps long first array item valid', () => {
            expect(stringifyWithLineWrap([['long-label', 'long-expression']], 16, 2)).toBe('[["long-label","long-expression"]]');
        });

        it('Keeps empty arrays valid', () => {
            expect(stringifyWithLineWrap([], 16, 2)).toBe('[]');
        });
    });

    describe('countRows', () => {
        it('Single line', () => {
            expect(countRows('abc')).toBe(1);
        });

        it('Multiple lines', () => {
            expect(countRows('a\nb\n')).toBe(3);
        });
    });

    describe('formatBytes', () => {
        it('Zero bytes', () => {
            expect(formatBytes(0)).toBe('0 B');
        });

        it('Formats with default three significant digits', () => {
            expect(formatBytes(1536)).toBe('1.50 KB');
            expect(formatBytes(126484480)).toBe('121 MB');
        });

        it('Keeps trailing zeros for significant digits', () => {
            expect(formatBytes(1024)).toBe('1.00 KB');
            expect(formatBytes(10240)).toBe('10.0 KB');
        });

        it('Formats with custom significant digits', () => {
            expect(formatBytes(1536, 2)).toBe('1.5 KB');
            expect(formatBytes(1536, 4)).toBe('1.500 KB');
            expect(formatBytes(126484480, 2)).toBe('121 MB');
        });
    });

    describe('formatNumberSmart', () => {
        it('Truncates integer part when it fills total length', () => {
            expect(formatNumberSmart(12345.67, 4)).toBe('1234');
        });

        it('Rounds decimal part within total length', () => {
            expect(formatNumberSmart(12.3456, 5)).toBe('12.35');
        });

        it('Honors max decimal places', () => {
            expect(formatNumberSmart(12.3456, 8, 1)).toBe('12.3');
        });
    });

    describe('formatName', () => {
        it('First last', () => {
            expect(formatName('Ada', 'Lovelace', 'first-last')).toBe('Ada Lovelace');
        });

        it('Last first', () => {
            expect(formatName('Ada', 'Lovelace', 'last-first')).toBe('Lovelace, Ada');
        });
    });

    describe('getFileExtension', () => {
        it('Lowercases extension', () => {
            expect(getFileExtension('Replay.AVF')).toBe('avf');
        });

        it('Uses final extension segment', () => {
            expect(getFileExtension('archive.tar.gz')).toBe('gz');
        });

        it('Hidden file without another dot has no extension', () => {
            expect(getFileExtension('.env')).toBe('');
        });

        it('Filename without dot has no extension', () => {
            expect(getFileExtension('README')).toBe('');
        });
    });

    describe('getSoftwareExtension', () => {
        it('Maps supported software codes', () => {
            expect(getSoftwareExtension('a')).toBe('.avf');
            expect(getSoftwareExtension('e')).toBe('.evf');
            expect(getSoftwareExtension('r')).toBe('.rmv');
            expect(getSoftwareExtension('m')).toBe('.mvf');
            expect(getSoftwareExtension('x')).toBe('.evf');
        });
    });
});
