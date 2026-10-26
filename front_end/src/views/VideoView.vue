<template>
    <div class="layout-row mb-4" style="margin-bottom: 10px;">
        <BaseButton v-for="level in MS_Levels" :key="level" type="warning" :plain="levelTagSelected != level" :aria-pressed="levelTagSelected == level" size="small" @click="levelTagSelected = level; request_videos();">
            {{ t(`level.${level}`) }}
        </BaseButton>
    </div>

    <div class="layout-row mb-4" style="margin-bottom: 10px;">
        <BaseButton
            v-for="(tag, key) in modeTags" :key="key" type="success" :plain="!(modeTagSelected == key)" :aria-pressed="modeTagSelected == key" size="small"
            @click="modeTagSelected = key as string; request_videos();"
        >
            {{ tag.name }}
        </BaseButton>
    </div>

    <div class="layout-row mb-4" style="margin-bottom: 10px;">
        <BaseButton
            v-for="(value, key) in indexTags" :key="key" type="primary" :plain="!value.selected" :aria-pressed="value.selected" size="small"
            @click="indexSelect(key, value)"
        >
            {{ t(`prop.${key}`) }}
        </BaseButton>
    </div>

    <div class="description-layout">
        <h3 class="description-title">
            {{ t('filter') }}
        </h3>
        <dl class="descriptions">
            <div class="description-item">
                <dt>{{ t('prop.state') }}</dt>
                <dd>
                    <VideoStateFilter v-model="videofilter.filter_state" @change="request_videos" />
                </dd>
            </div>
            <div class="description-item">
                <dt>{{ t('nf') }}</dt>
                <dd>
                    <ElSwitch v-model="nfOnly" @change="state.CurrentPage = 1; request_videos();" />
                </dd>
            </div>
            <div class="description-item">
                <dt>{{ t('prop.bbbv') }}</dt>
                <dd>
                    <BBBVFilter :level="levelTagSelected" @change="request_videos" />
                </dd>
            </div>
        </dl>
    </div>
    <div style="font-size:20px;margin: auto;margin-top: 10px;">
        <ElTable :data="videoList" border table-layout="auto" @sort-change="handleSortChange" @row-click="previewVideo">
            <VideoViewState />
            <ElTableColumn type="index" :index="offsetIndex" fixed />
            <VideoViewRealname />
            <ElTableColumn
                v-for="key in selected_index()" :key="key" v-slot="scope" :prop="indexTags[key].key"
                :label="t(`prop.${key}`)" sortable="custom"
                :sort-orders="indexTags[key].reverse ? (['descending', 'ascending']) : (['ascending', 'descending'])"
            >
                <span class="nobr">
                    {{ columnFormatter(key, scope.row[indexTags[key].key]) }}
                </span>
            </ElTableColumn>
        </ElTable>
    </div>

    <div style="margin-top: 16px;">
        <ElPagination :current-page="state.CurrentPage" :page-sizes="[20, 50, 100]" :page-size="videofilter.pagesize" layout="total, sizes, prev, pager, next, jumper" :total="state.VideoCount" @size-change="handleSizeChange" @current-change="handleCurrentChange" />
    </div>
</template>

<script lang="ts" setup>
import '@/styles/descriptions.css';
import '@/styles/layout.css';
// 全网录像的检索器，根据三个维度排序
import type { TableColumnCtx } from 'element-plus';
import { ElPagination, ElSwitch, ElTable, ElTableColumn } from 'element-plus';
import { onMounted, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';

import BaseButton from '@/components/common/BaseButton.vue';
import BBBVFilter from '@/components/Filters/BBBVFilter.vue';
import VideoStateFilter from '@/components/Filters/VideoStateFilter.vue';
import { httpErrorNotification } from '@/components/Notifications';
import VideoViewRealname from '@/components/tableColumns/VideoViewRealname.vue';
import VideoViewState from '@/components/tableColumns/VideoViewState.vue';
import { fetchVideoInfos, videoDisplayFields } from '@/services/videoInfoService';
import type { VideoMetadata } from '@/services/videoInfoService';
import { videofilter } from '@/store';
import { ms_to_s } from '@/utils';
import { preview } from '@/utils/common/PlayerDialog';
import useCurrentInstance from '@/utils/common/useCurrentInstance';
import { MS_Levels } from '@/utils/ms_const';
import type { MS_Level, MS_Software } from '@/utils/ms_const';
import { utc_to_local_format } from '@/utils/system/tools';

const { proxy } = useCurrentInstance();
const { t } = useI18n();

const levelTagSelected = ref<MS_Level>('e');
const modeTagSelected = ref('STD');
const nfOnly = ref(false);
const indexTagSelected = ref('timems');

const indexVisible = ref(true);

const state = reactive({
    tableLoading: false,
    CurrentPage: 1,
    VideoCount: 0,
    ReverseOrder: false,
    Total: 3,
});

// const test  = reactive({v: 5});
const videoList = reactive<Video[]>([]);
// 带下划线与不带的至少存在一个
type VideoFieldValue = string | number | boolean | null | undefined | string[];
type Video = Record<string, VideoFieldValue> & { id: number; software: MS_Software };
type NameKey = Record<string, string>;
type Tags = Record<string, NameKey>;
type TableSortOrder = 'ascending' | 'descending';
interface NameKeyReverse {
    key: string;
    reverse: boolean;
    to_fixed: number;
    selected: boolean;
}
type TagsReverse = Record<string, NameKeyReverse>;

interface VideoQueryResponse {
    count: number;
    videos: (VideoMetadata & { player__id: number; player__realname: string })[];
}

interface VideoQueryParams {
    level: MS_Level;
    mode: string;
    nf: boolean;
    o: string;
    r: boolean;
    ps: number;
    page: number;
    bmin: number;
    bmax: number;
    s?: string[];
}

interface SortChange {
    column: TableColumnCtx<Video>;
    prop: string | null;
    order: TableSortOrder | null;
}

const modeTags: Tags = {
    STD: { name: '标准', key: '00' },
    // "UPK": { name: "UPK", key: "01" },
    WQI: { name: 'Win7', key: '04' },
    JSW: { name: '竞速无猜', key: '05' },
    QWC: { name: '强无猜', key: '06' },
    RWC: { name: '弱无猜', key: '07' },
    // "ZWC": { name: "准无猜", key: "08" },
    // "QKC": { name: "强可猜", key: "09" },
    // "RKC": { name: "弱可猜", key: "10" },
    // "BZD": { name: "递归", key: "11" }
};

// reverse: true从小到大
const indexTags: TagsReverse = reactive({
    upload_time: { key: 'upload_time', reverse: true, to_fixed: -1, selected: true },
    timems: { key: 'timems', reverse: false, to_fixed: 3, selected: true },
    bbbv: { key: 'bv', reverse: false, to_fixed: 0, selected: true },
    bbbv_s: { key: 'bvs', reverse: true, to_fixed: 3, selected: true },
    left_s: { key: 'left_s', reverse: true, to_fixed: 3, selected: false },
    right_s: { key: 'right_s', reverse: true, to_fixed: 3, selected: false },
    double_s: { key: 'double_s', reverse: true, to_fixed: 3, selected: false },
    cl_s: { key: 'cl_s', reverse: true, to_fixed: 3, selected: false },
    path: { key: 'path', reverse: false, to_fixed: 2, selected: false },
    stnb: { key: 'stnb', reverse: true, to_fixed: 2, selected: true },
    ioe: { key: 'ioe', reverse: true, to_fixed: 3, selected: false },
    thrp: { key: 'thrp', reverse: true, to_fixed: 3, selected: false },
    ce_s: { key: 'ce_s', reverse: true, to_fixed: 3, selected: false },
    op: { key: 'op', reverse: false, to_fixed: 0, selected: false },
    is: { key: 'isl', reverse: false, to_fixed: 0, selected: false },
    cell1: { key: 'cell1', reverse: false, to_fixed: 0, selected: false },
    cell2: { key: 'cell2', reverse: false, to_fixed: 0, selected: false },
    cell3: { key: 'cell3', reverse: false, to_fixed: 0, selected: false },
    cell4: { key: 'cell4', reverse: false, to_fixed: 0, selected: false },
    cell5: { key: 'cell5', reverse: false, to_fixed: 0, selected: false },
    cell6: { key: 'cell6', reverse: false, to_fixed: 0, selected: false },
    cell7: { key: 'cell7', reverse: false, to_fixed: 0, selected: false },
    cell8: { key: 'cell8', reverse: false, to_fixed: 0, selected: false },
});

function selected_index(): string[] {
    const list = [];
    for (const key of Object.keys(indexTags)) {
        if (indexTags[key].selected) {
            list.push(key);
        }
    }
    return list;
}

function previewVideo(row: Video): void {
    void preview(row.id, row.software);
}

function columnFormatter(key: string, value: VideoFieldValue | undefined): string | number | boolean | null | undefined {
    if (Array.isArray(value)) return value.join(',');
    if (key == 'upload_time') {
        if (value === null || value === undefined) return value;
        return utc_to_local_format(String(value));
    } else if (key == 'timems') {
        if (typeof value !== 'number') return '-';
        return ms_to_s(value);
    } else if (key == 'name') {
        return value;
    } else if (value === null || typeof value === 'boolean') {
        return value;
    } else {
        return to_fixed_n(value, indexTags[key].to_fixed);
    }
}

onMounted(() => {
    document.getElementsByClassName('el-pagination__goto')[0].childNodes[0].nodeValue = '转到';
    // 把分页器的go to改成中文。
    mod_style();
    request_videos();
});

function to_fixed_n(input: string | number | undefined, to_fixed: number): string | number | undefined {
    // 返回保留to_fixed位小数的字符串，四舍六入五取双
    if (input === undefined) return input;
    if (to_fixed <= 0) return input;
    if (typeof input == 'string') return parseFloat(input).toFixed(to_fixed);
    return input.toFixed(to_fixed);
}

function mod_style(): void {
    // 调整列宽样式
    // console.log(indexVisible.value);

    indexVisible.value = !['upload_time', 'bbbv', 'bbbv_s', 'timems'].
        includes(indexTagSelected.value);
}

const prevColumn = ref<TableColumnCtx<Video> | null>(null); // 上一个排序列
function handleSortChange(sort: SortChange): void {
    for (const key of Object.keys(indexTags)) { // 找到对应的key。很丑陋，but it works
        if (indexTags[key].key == sort.prop) {
            if (key != indexTagSelected.value) { // 改变了排序列，清除之前列的排序
                if (prevColumn.value != null) {
                    prevColumn.value.order = null;
                }
                indexTagSelected.value = key;
            }
            if (sort.order == null) { // 不允许通过点击箭头的方式将排序变成 null
                sort.column.order = state.ReverseOrder ? 'descending' : 'ascending';
            }
            state.ReverseOrder = sort.column.order == 'descending';
            break;
        }
    }
    prevColumn.value = sort.column;
    request_videos();
}

function handleSizeChange(val: number): void {
    videofilter.value.pagesize = val;
    request_videos();
}

function handleCurrentChange(val: number): void {
    state.CurrentPage = val;
    request_videos();
}

function offsetIndex(index: number): number {
    return index + 1 + (state.CurrentPage - 1) * videofilter.value.pagesize;
}

// 根据配置，刷新当前页面的录像表
let queryRevision = 0;
function request_videos(): void {
    const revision = ++queryRevision;
    const [bmin, bmax] = videofilter.value.bbbv_range[levelTagSelected.value];
    const sortField = indexTags[indexTagSelected.value].key;
    const params: VideoQueryParams = {
        level: levelTagSelected.value,
        mode: modeTags[modeTagSelected.value].key,
        nf: nfOnly.value,
        o: sortField === 'stnb' ? 'iqg' : sortField,
        r: state.ReverseOrder,
        ps: videofilter.value.pagesize,
        page: state.CurrentPage,
        bmin: bmin,
        bmax: bmax,
    };
    if (![0, 4].includes(videofilter.value.filter_state.length)) {
        params.s = videofilter.value.filter_state;
    }
    void proxy.$axios.get<VideoQueryResponse>('/api/video/query', {
        params: params,
    }).then(async function (response) {
        const { data } = response;
        const videos = await fetchVideoInfos(data.videos);
        if (revision !== queryRevision) return;
        videoList.length = 0;
        for (const row of videos) videoList.push({ ...videoDisplayFields(row), ...row });
        state.VideoCount = data.count;
    }).catch(httpErrorNotification);
}

function indexSelect(key: string | number, value: NameKeyReverse): void {
    indexTags[key].selected = !value.selected;
}
</script>

<style lang="less" scoped>
.rank {
    width: 5%;
    display: inline-block;
    text-align: center;
}

.utime {
    width: 25%;
    min-width: 200px;
    display: inline-block;
    text-align: center;
}

.bbbv_bbbvs_rtime {
    width: 13%;
    min-width: 100px;
    display: inline-block;
    text-align: center;
}

.index {
    width: 13%;
    min-width: 100px;
    display: inline-block;
    text-align: center;
    // cursor: pointer;
}

.hoverable:hover {
    // color: rgb(64, 158, 255);
    cursor: pointer;
}

.el-pagination {
    justify-content: center;
}

.row {
    padding-top: 6px;
    padding-bottom: 6px;
}

.row:hover {
    background-color: #eee;
}

.inline-div {
    display: inline-block;
    margin: 0;
}

.nobr {
    white-space: nowrap;
    hyphens: none;
}
</style>
