/**
 * @description 把时间戳从UTC转为当地时间
 * @param {String} t 需要转换的时间戳
 */
export function utc_to_local_format(t: string | Date = '2024-01-10T14:03:09Z'): string {
    const utc_time = new Date(t);
    return utc_time.toLocaleString('default', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    }).replace(/\//g, '-');
}

// credit: https://stackoverflow.com/a/5767357/12144822
export function removeItem<T>(arr: T[], value: T): T[] {
    const index = arr.indexOf(value);
    if (index > -1) {
        arr.splice(index, 1);
    }
    return arr;
}
