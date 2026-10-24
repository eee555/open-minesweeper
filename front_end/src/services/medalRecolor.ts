export type MedalTone = 'b' | 'i';

const cache = new Map<string, Promise<string>>();

function mixChannel(channel: number, aim: number) {
    return Math.min(255, Math.max(0, Math.trunc(channel * 0.2 + aim * 0.8)));
}

/** 只改偏金的像素。白高光和蓝青色中心保持原色。与原先生成铜、银底图的公式相同。 */
export function recolorMedalPixels(data: Uint8ClampedArray, metal: MedalTone): void {
    const silver = metal === 'i';
    for (let index = 0; index < data.length; index += 4) {
        const red = data[index];
        const green = data[index + 1];
        const blue = data[index + 2];
        const alpha = data[index + 3];
        if (alpha < 8 || (red > 230 && green > 220 && blue > 200) || red <= blue + 25 || red < 70) continue;
        const luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue;
        const target = silver
            ? [luminance * 0.9 + 16, luminance * 0.94 + 18, luminance + 24]
            : [luminance * 1.12 + 36, luminance * 0.52 + 8, luminance * 0.2];
        data[index] = mixChannel(red, target[0]);
        data[index + 1] = mixChannel(green, target[1]);
        data[index + 2] = mixChannel(blue, target[2]);
    }
}

function loadImage(src: string) {
    return new Promise<HTMLImageElement>((resolve, reject) => {
        const image = new Image();
        image.onload = () => {
            resolve(image);
        };
        image.onerror = () => {
            reject(new Error(src));
        };
        image.src = src;
    });
}

async function recolorToUrl(src: string, metal: MedalTone) {
    const image = await loadImage(src);
    const canvas = document.createElement('canvas');
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    const context = canvas.getContext('2d', { willReadFrequently: true });
    if (!context) return src;
    context.drawImage(image, 0, 0);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
    recolorMedalPixels(pixels.data, metal);
    context.putImageData(pixels, 0, 0);
    const blob = await new Promise<Blob | null>((resolve) => {
        canvas.toBlob(resolve, 'image/png');
    });
    return blob ? URL.createObjectURL(blob) : src;
}

export function recolorMedalUrl(src: string, metal: MedalTone): Promise<string> {
    const key = `${metal}:${src}`;
    const cached = cache.get(key);
    if (cached) return cached;
    const pending = recolorToUrl(src, metal);
    cache.set(key, pending);
    return pending;
}
