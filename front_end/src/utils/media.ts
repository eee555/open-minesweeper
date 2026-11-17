/** 展示地址仅由前端生成；GitHub 仓库的当前地址需按数字 ID 单独获取。 */
export function mediaExternalUrl(format: string, suffix: string): string | undefined {
    const id = encodeURIComponent(suffix);
    switch (format) {
        case 'B_v': return `https://www.bilibili.com/video/${id}/`;
        case 'B_a': return `https://www.bilibili.com/read/cv${id}`;
        case 'c_p': return `https://saolei.wang/bbs/${id}`;
        default: return undefined;
    }
}

export function mediaEmbedUrl(format: string, suffix: string): string | undefined {
    return format === 'B_v' ? `https://player.bilibili.com/player.html?bvid=${encodeURIComponent(suffix)}&page=1&autoplay=0&danmaku=0` : undefined;
}
