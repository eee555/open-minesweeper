import type { MS_Software } from './ms_const';

export { default as ControlRegex } from '@unicode/unicode-16.0.0/General_Category/Control/regex.mjs';
export { default as MarkRegex } from '@unicode/unicode-16.0.0/General_Category/Mark/regex.mjs';
export { default as LineSeparatorRegex } from '@unicode/unicode-16.0.0/General_Category/Line_Separator/regex.mjs';
export { default as ParagraphSeparatorRegex } from '@unicode/unicode-16.0.0/General_Category/Paragraph_Separator/regex.mjs';
export { default as SpaceSeparatorRegex } from '@unicode/unicode-16.0.0/General_Category/Space_Separator/regex.mjs';

// credit: ChatGPT
export function stringifyWithLineWrap(
    obj: unknown,
    maxLineLength = 80,
    indent = 2,
): string {
    const INDENTATION = ' '.repeat(indent);

    function processValue(value: unknown, currentIndent: string): string {
        if (Array.isArray(value)) {
            if (value.length === 0) return '[]';

            let line = '[';
            const lines: string[] = [];
            for (const v of value) {
                const itemStr = JSON.stringify(v) ?? 'undefined';
                if (line !== '[' && line.length + itemStr.length + 2 > maxLineLength) {
                    lines.push(line.trimEnd() + ',');
                    line = currentIndent + INDENTATION + itemStr;
                } else {
                    line += (line === '[' ? '' : ', ') + itemStr;
                }
            }
            if (line !== '[') lines.push(line.trimEnd());
            return lines.join('\n') + ']';
        } else if (typeof value === 'object' && value !== null) {
            const objectValue = value as Record<string, unknown>;
            const keys = Object.keys(objectValue);
            let result = '{\n';
            for (const key of keys) {
                const keyValue = JSON.stringify(key) + ': ' + processValue(objectValue[key], currentIndent + INDENTATION);
                result += currentIndent + INDENTATION + keyValue + ',\n';
            }
            result = result.replace(/,\n$/, '\n'); // Remove trailing comma
            result += currentIndent + '}';
            return result;
        } else {
            return JSON.stringify(value);
        }
    }

    return processValue(obj, '');
}

export function countRows(str: string): number {
    return str.split('\n').length;
}

export function formatBytes(bytes: number, significant = 3): string {
    if (bytes === 0) return '0 B';

    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];

    const i = Math.floor(Math.log(bytes) / Math.log(k));
    const value = bytes / Math.pow(k, i);
    const integerDigits = Math.floor(value).toString().length;
    const decimalPlaces = Math.max(significant - integerDigits, 0);

    return value.toFixed(decimalPlaces) + ' ' + sizes[i];
}

export function formatNumberSmart(
    num: number,
    totalLength: number,
    maxDecimalPlaces = Infinity,
): string {
    // 分离整数和小数部分
    const [integerPart] = num.toString().split('.');

    // 如果整数部分已经超过或等于总长度
    if (integerPart.length >= totalLength) {
        return integerPart.substring(0, totalLength);
    }

    // 计算小数部分可用的长度
    const availableDecimalLength = totalLength - integerPart.length - 1; // -1 给小数点

    if (availableDecimalLength <= 0) {
        return integerPart; // 没有空间显示小数部分
    }

    // 确定实际使用的小数位数
    const actualDecimalPlaces = Math.min(availableDecimalLength, maxDecimalPlaces); // 同时受总长度和最大小数位数限制

    if (actualDecimalPlaces <= 0) return integerPart;

    // 使用 toFixed 并确保不超过实际小数位数
    const rounded = num.toFixed(actualDecimalPlaces);

    // 确保不超过总长度（toFixed 可能因为四舍五入进位导致长度变化）
    return rounded.length > totalLength ? rounded.substring(0, totalLength) : rounded;
}

export function formatName(firstname: string, lastname: string, mode: 'first-last' | 'last-first'): string {
    if (mode === 'first-last') {
        return `${firstname} ${lastname}`;
    } else {
        return `${lastname}, ${firstname}`;
    }
}

/**
 * 获取文件名的扩展名（不含点号）
 * @param filename - 文件名（可包含路径）
 * @returns 扩展名（小写），若无扩展名则返回空字符串
 * @example
 * getFileExtension("document.pdf") // "pdf"
 * getFileExtension("archive.tar.gz") // "gz"
 * getFileExtension(".hiddenfile") // ""
 * getFileExtension("noextension") // ""
 * getFileExtension("path/to/file.txt") // "txt"
 */
export function getFileExtension(filename: string): string {
    // 提取最后一个点号之后的部分
    const lastDotIndex = filename.lastIndexOf('.');

    // 如果没有点号，或者点号在开头（隐藏文件），返回空字符串
    if (lastDotIndex <= 0) {
        return '';
    }

    // 返回点号后的部分，并转为小写
    return filename.slice(lastDotIndex + 1).toLowerCase();
}

export function getSoftwareExtension(software: MS_Software): '.avf' | '.evf' | '.rmv' | '.mvf' {
    switch (software) {
        case 'a': return '.avf';
        case 'e': return '.evf';
        case 'r': return '.rmv';
        case 'm': return '.mvf';
        case 'x': return '.evf';
    }
}
