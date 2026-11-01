import { DEFAULT_MEDAL_COLORS, MAX_MEDAL_PALETTE_JSON_LENGTH, defaultMedalPalette, loadMedalPalette, medalPaletteColor, normalizeMedalColor, parseMedalPalette, saveMedalPalette } from '../../../../front_end/src/services/medalPalette';
import type { PaletteStorage } from '../../../../front_end/src/services/medalPalette';

interface Stage { stage: number; label: string; tier: number }
interface ReviewData { assets: Record<string, { mime: string; base64: string }>; stages: Stage[] }
const $ = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const data: ReviewData = JSON.parse($('review-data').textContent ?? '{}');
const code = 'ability.time.b';
const urls: Record<string, string> = {};
for (const [name, asset] of Object.entries(data.assets)) {
    urls[name] = URL.createObjectURL(new Blob([Uint8Array.from(atob(asset.base64), (c) => c.charCodeAt(0))], { type: asset.mime }));
}
let storage: PaletteStorage | undefined;
try { storage = window.localStorage; } catch { /* Denied file-origin or private storage. */ }
const loaded = loadMedalPalette(storage);
let config = loaded.config;
let shapeDifficulty = 1;
const namespace = 'http://www.w3.org/2000/svg';
// Machado et al. (2009), severity 1.0; apply to linear RGB, not encoded sRGB.
const matrices: Record<string, number[]> = {
    protanopia: [0.152286, 1.052583, -0.204868, 0.114503, 0.786281, 0.099216, -0.003882, -0.048116, 1.051998],
    deuteranopia: [0.367322, 0.860646, -0.227968, 0.280085, 0.672501, 0.047413, -0.011820, 0.042940, 0.968881],
    tritanopia: [1.255528, -0.076749, -0.178779, -0.078411, 0.930809, 0.147602, 0.004733, 0.691367, 0.303900],
};

function svg(tag: string, attrs: Record<string, string>): SVGElement {
    const element = document.createElementNS(namespace, tag);
    for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value);
    return element;
}

function toneFilter(id: string, color: string) {
    const previous = document.getElementById(id);
    previous?.remove();
    const filter = svg('filter', { id, 'color-interpolation-filters': 'sRGB' });
    filter.append(svg('feColorMatrix', { type: 'saturate', values: '0' }));
    const transfer = svg('feComponentTransfer', {});
    const channels = [1, 3, 5].map((offset) => Number.parseInt(color.slice(offset, offset + 2), 16) / 255);
    for (const [index, name] of ['R', 'G', 'B'].entries()) {
        const value = channels[index];
        transfer.append(svg('feFunc' + name, { type: 'table', tableValues: [0, value * 0.28, value * 0.62, value, value + (1 - value) * 0.45, 1].map((n) => n.toFixed(6)).join(' ') }));
    }
    filter.append(transfer);
    $('filters').append(filter);
}

for (const [id, matrix] of Object.entries(matrices)) {
    const filter = svg('filter', { id, 'color-interpolation-filters': 'linearRGB' });
    filter.append(svg('feColorMatrix', { type: 'matrix', values: [...matrix.slice(0, 3), 0, 0, ...matrix.slice(3, 6), 0, 0, ...matrix.slice(6, 9), 0, 0, 0, 0, 0, 1, 0].join(' ') }));
    $('filters').append(filter);
}

function medal(filter: string, size: number, label: string, difficulty: number | 'shape' = 'shape'): HTMLElement {
    const shell = document.createElement('span');
    shell.className = 'medal-shell';
    const composition = document.createElement('span');
    composition.className = 'medal-composition';
    const art = document.createElement('span');
    art.className = 'medal';
    art.style.setProperty('--size', size + 'px');
    art.style.setProperty('--tone-filter', `url(#${filter})`);
    art.setAttribute('role', 'img');
    art.setAttribute('aria-label', label + '，' + (difficulty === 'shape' ? shapeDifficulty : difficulty) + ' 星难度');
    if (difficulty === 'shape') art.dataset.shapeLabel = label;
    const body = document.createElement('img');
    body.className = 'body'; body.alt = ''; body.src = urls.base;
    const stars = document.createElement('img');
    stars.className = 'star'; stars.alt = ''; stars.src = urls['star' + (difficulty === 'shape' ? shapeDifficulty : difficulty)];
    if (difficulty === 'shape') stars.dataset.shapeStar = '';
    art.append(body, stars); composition.append(art); shell.append(composition);
    return shell;
}

function openZoom(filter: string, title: string, difficulty: number | 'shape' = 'shape') {
    $('zoom-title').textContent = title;
    $('zoom-image').replaceChildren(medal(filter, 420, title, difficulty));
    $('zoom-caption').textContent = '星数表示难度；色档编号和门槛表达成绩。自定义颜色不会改变它们。';
    $('zoom-image').dataset.filter = filter;
    $('zoom-image').dataset.difficulty = String(difficulty);
    $('zoom-title').dataset.original = title;
    $('zoom').setAttribute('aria-label', title);
    ($('zoom') as HTMLDialogElement).showModal();
}

function colorControls(parent: HTMLElement, key: string, label: string, onChange: (value: string) => void) {
    const controls = document.createElement('div'); controls.className = 'controls';
    const picker = document.createElement('input'); picker.type = 'color'; picker.dataset.key = key; picker.dataset.picker = ''; picker.setAttribute('aria-label', label + '取色器');
    const hex = document.createElement('input'); hex.type = 'text'; hex.className = 'hex'; hex.maxLength = 7; hex.spellcheck = false; hex.dataset.key = key; hex.dataset.hex = ''; hex.setAttribute('aria-label', label + ' HEX 色值');
    const apply = (input: HTMLInputElement) => {
        try {
            const value = normalizeMedalColor(input.value);
            hex.removeAttribute('aria-invalid'); $('error').textContent = '';
            onChange(value); changed();
        } catch (error) {
            hex.setAttribute('aria-invalid', 'true');
            $('error').textContent = error instanceof Error ? error.message : '颜色无效。';
        }
    };
    picker.oninput = () => apply(picker);
    hex.onchange = () => apply(hex);
    controls.append(picker, hex); parent.append(controls);
    return controls;
}

for (let tier = 1; tier <= 5; tier++) {
    const row = document.createElement('div'); row.className = 'color-row';
    row.innerHTML = `<div class="color-row-heading"><strong>色档 ${tier}</strong><small>${data.stages.filter((stage) => stage.tier === tier).map((stage) => stage.label).join(' / ')}</small></div>`;
    const controls = colorControls(row, 'tier-' + tier, '色档 ' + tier, (color) => { config.colors[tier - 1] = color; });
    const reset = document.createElement('button'); reset.className = 'reset-one'; reset.textContent = '默认'; reset.setAttribute('aria-label', '恢复色档 ' + tier + '默认颜色');
    reset.onclick = () => { config.colors[tier - 1] = DEFAULT_MEDAL_COLORS[tier - 1]; changed(); };
    controls.append(reset); $('color-settings').append(row);

    const card = document.createElement('article'); card.className = 'tier-card';
    card.innerHTML = `<h3>色档 ${tier}</h3><span class="swatch preview-color" data-swatch="${tier}"></span><small data-color-label="${tier}"></small>`;
    const zoom = document.createElement('button'); zoom.className = 'zoom'; zoom.setAttribute('aria-label', '放大色档 ' + tier);
    const shell = medal('tier-' + tier, 140, 'Time 破境，色档 ' + tier);
    shell.querySelector('.medal')?.classList.add('hero-medal');
    zoom.append(shell); zoom.onclick = () => openZoom('tier-' + tier, 'Time 破境 · 色档 ' + tier);
    card.append(zoom);
    const thresholds = document.createElement('p'); thresholds.className = 'thresholds'; thresholds.textContent = data.stages.filter((stage) => stage.tier === tier).map((stage) => stage.label).join(' / ');
    card.append(thresholds); $('tier-cards').append(card);
}

for (const stage of data.stages) {
    const label = `初级破境 · ${stage.label} · 色档 ${stage.tier}`;
    const row = document.createElement('article'); row.className = 'stage';
    const zoom = document.createElement('button'); zoom.className = 'zoom'; zoom.setAttribute('aria-label', '放大' + label);
    zoom.append(medal('stage-' + stage.stage, 72, label, 1)); zoom.onclick = () => openZoom('stage-' + stage.stage, label, 1);
    row.append(zoom);
    const text = document.createElement('strong'); text.textContent = stage.label;
    const caption = document.createElement('small'); caption.textContent = '初级 · 色档 ' + stage.tier;
    const tag = document.createElement('span'); tag.className = 'tag'; tag.dataset.overrideTag = String(stage.stage);
    row.append(text, caption, tag); $('stages').append(row);

    const override = document.createElement('div'); override.className = 'override';
    override.innerHTML = `<strong>${stage.label}</strong><small>初级 · 色档 ${stage.tier}</small>`;
    const controls = colorControls(override, 'stage-' + stage.stage, stage.label, (color) => {
        config.stages[code] ??= {};
        config.stages[code][String(stage.stage)] = color;
    });
    const clear = document.createElement('button'); clear.className = 'reset-one'; clear.textContent = '跟随色档'; clear.dataset.clearStage = String(stage.stage);
    clear.onclick = () => {
        if (config.stages[code]) {
            delete config.stages[code][String(stage.stage)];
            if (!Object.keys(config.stages[code]).length) delete config.stages[code];
        }
        changed();
    };
    controls.append(clear); $('overrides').append(override);
}

function luminance(color: string) {
    const rgb = [1, 3, 5].map((offset) => Number.parseInt(color.slice(offset, offset + 2), 16) / 255).map((v) => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
    return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
}

function updateAll() {
    const effective: Record<string, string> = {};
    config.colors.forEach((color, index) => {
        const tier = index + 1;
        effective['tier-' + tier] = color;
        toneFilter('tier-' + tier, color);
        document.querySelector<HTMLElement>(`[data-swatch="${tier}"]`)!.style.backgroundColor = color;
        document.querySelector<HTMLElement>(`[data-color-label="${tier}"]`)!.textContent = color;
    });
    for (const stage of data.stages) {
        const color = medalPaletteColor(config, stage.tier, code, stage.stage)!;
        effective['stage-' + stage.stage] = color;
        toneFilter('stage-' + stage.stage, color);
        const overridden = Object.hasOwn(config.stages[code] ?? {}, String(stage.stage));
        document.querySelector<HTMLElement>(`[data-override-tag="${stage.stage}"]`)!.textContent = overridden ? '单独设色' : '跟随色档';
        document.querySelector<HTMLButtonElement>(`[data-clear-stage="${stage.stage}"]`)!.disabled = !overridden;
    }
    document.querySelectorAll<HTMLInputElement>('input[data-key]').forEach((input) => { input.value = effective[input.dataset.key!]; input.removeAttribute('aria-invalid'); });
    const brightness = config.colors.map(luminance);
    const ordered = brightness.every((value, index) => index === 0 || value > brightness[index - 1] + 0.005);
    const distinct = new Set(config.colors).size === 5;
    $('palette-health').textContent = !distinct
        ? '有色档使用了相同颜色。色档编号与具体门槛仍可辨识，建议结合色觉模拟检查。'
        : ordered ? '当前五档基色亮度依次提升。请同时检查实际勋章、色觉模拟与小尺寸；文字线索始终保留。'
            : '自定义后基色明暗不再逐档递增。可以保留个人偏好；色档编号与门槛仍负责表达成绩顺序。';
}

function changed() {
    updateAll(); $('error').textContent = '';
    $('storage-status').textContent = saveMedalPalette(storage, config)
        ? '配色已保存在此浏览器，重新打开可恢复。'
        : '本次预览已生效，但浏览器无法保存。可导出 JSON 备份。';
}

function updateSizes() {
    const tier = Number(($('size-tier') as HTMLSelectElement).value);
    $('sizes').replaceChildren(...[32, 40, 48, 64, 72].map((size) => {
        const figure = document.createElement('figure'); figure.append(medal('tier-' + tier, size, `Time 色档 ${tier}，${size} 像素`));
        const caption = document.createElement('figcaption'); caption.textContent = size + 'px'; figure.append(caption); return figure;
    }));
}

$('theme').onclick = () => { $('theme').setAttribute('aria-pressed', String(document.body.classList.toggle('dark'))); };
$('vision').onchange = () => {
    const mode = ($('vision') as HTMLSelectElement).value;
    document.body.style.setProperty('--vision-filter', mode === 'normal' ? 'none' : mode === 'gray' ? 'grayscale(1)' : `url(#${mode})`);
};
$('difficulty').onchange = () => {
    shapeDifficulty = Number(($('difficulty') as HTMLSelectElement).value);
    document.querySelectorAll<HTMLImageElement>('[data-shape-star]').forEach((image) => { image.src = urls['star' + shapeDifficulty]; });
    document.querySelectorAll<HTMLElement>('[data-shape-label]').forEach((element) => { element.setAttribute('aria-label', element.dataset.shapeLabel + '，' + shapeDifficulty + ' 星难度'); });
};
$('size-tier').onchange = updateSizes;
$('reset').onclick = () => { config = defaultMedalPalette(); changed(); };
$('export').onclick = () => {
    const blob = new Blob([JSON.stringify(config, null, 2) + '\n'], { type: 'application/json' });
    const address = URL.createObjectURL(blob);
    const anchor = document.createElement('a'); anchor.href = address; anchor.download = 'medal-palette.json'; anchor.click();
    setTimeout(() => URL.revokeObjectURL(address), 10000);
};
$('import').onclick = () => ($('import-file') as HTMLInputElement).click();
$('import-file').onchange = async () => {
    const input = $('import-file') as HTMLInputElement;
    const file = input.files?.[0]; if (!file) return;
    try {
        if (file.size > MAX_MEDAL_PALETTE_JSON_LENGTH) throw new Error('配色文件不能超过 64 KiB。');
        const parsed = parseMedalPalette(await file.text());
        config = parsed; changed();
    } catch (error) {
        $('error').textContent = '导入失败：' + (error instanceof Error ? error.message : String(error));
    } finally { input.value = ''; }
};
$('close-zoom').onclick = () => ($('zoom') as HTMLDialogElement).close();
$('zoom').addEventListener('click', (event) => {
    if (event.target !== $('zoom')) return;
    const rect = $('zoom').getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) ($('zoom') as HTMLDialogElement).close();
});

updateAll(); updateSizes();
$('storage-status').textContent = loaded.status === 'saved' ? '已恢复此浏览器保存的配色。'
    : loaded.status === 'invalid' ? '已保存的配色格式无效，本次显示默认方案。'
        : loaded.status === 'unavailable' ? '浏览器无法访问本地存储，可用 JSON 备份配色。' : '当前为默认方案，修改后自动保存在此浏览器。';
