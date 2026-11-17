import type { DBSchema, IDBPDatabase, IDBPTransaction } from 'idb';
import { openDB } from 'idb';

export const CACHE_DB_NAME = 'saolei-cache';
export const CACHE_DB_VERSION = 2;

export const META_STORE_NAME = 'meta';
export const USER_INFO_STORE_NAME = 'user-info';
export const VIDEO_INFO_STORE_NAME = 'video-info';

const STORE_VERSIONS_KEY = 'storeVersions';
const ROW_SCHEMAS_KEY = 'rowSchemas';

interface CacheStoreDefinition {
    name: string;
    keyPath: string | readonly string[];
    version: number;
    indexes?: readonly {
        name: string;
        keyPath: string | readonly string[];
        options?: IDBIndexParameters;
    }[];
}

type CacheRowColumnType = 'array' | 'boolean' | 'number' | 'object' | 'string' | 'unknown';

interface CacheRowColumnDefinition {
    type: CacheRowColumnType;
    default?: unknown;
}

export type CacheRowSchema = Record<string, CacheRowColumnDefinition>;

/**
 * 前端缓存数据库维护说明：
 *
 * 1. 新增一张缓存表：
 *    - 添加一个 STORE_NAME 常量。
 *    - 在 CACHE_STORE_DEFINITIONS 中登记 keyPath、index 和兜底缓存版本。
 *    - 如果需要完整类型提示，在 SaoleiCacheDB 中添加该 store 的 key 类型；value 保持 unknown。
 *    - 在对应 service 的模块顶层调用 registerStoreRowSchema，声明运行时 row schema。
 *
 * 2. 修改 IndexedDB 结构：
 *    - 结构指 object store、keyPath 和 index，不包括普通业务字段。
 *    - 例如新增/删除 object store，或给已有 store 增删 index 时，必须递增 CACHE_DB_VERSION。
 *    - upgrade 回调会读取 CACHE_STORE_DEFINITIONS，自动创建 store，并同步 index。
 *    - 同步 index 时会删除未在 CACHE_STORE_DEFINITIONS 中声明的旧 index，因此必须显式保留所有仍在使用的 index。
 *    - keyPath 不能对已有 store 原地修改；这类变化通常需要新建 store 或清空旧 store 后重建。
 *
 * 3. 修改某张表的缓存数据格式，但不改变 IndexedDB 结构：
 *    - 优先修改对应 service 中 registerStoreRowSchema 的定义。
 *    - getDatabase 会对比 meta 中保存的旧 row schema 和当前 row schema，并尝试逐行迁移。
 *    - 新增字段必须在 row schema 中提供 default；删除字段会在迁移后丢弃；类型变化会按目标 type 转换。
 *    - 如果迁移过程出错，例如新增字段没有 default 或类型无法转换，会输出 warning 并清空对应 store，不影响其他 store。
 *
 * 4. database.ts 只管理 IndexedDB 结构，不定义业务字段：
 *    - 业务 row 类型在对应 service 中定义或引用。
 *    - 从数据库读取 unknown 后，在 service 中收窄为业务类型。
 *    - registerStoreRowSchema 定义的是运行时 schema，不是 TypeScript 类型本身。
 *
 * 5. CACHE_STORE_DEFINITIONS.version 是兜底清空开关：
 *    - 当某个 store 的缓存无法或不值得迁移时，递增该 store 的 version。
 *    - getDatabase 会只清空 version 变化的 store，并保留其他 store。
 *
 * 6. meta store 是内部 key-value 元信息表：
 *    - storeVersions 记录各 store 的兜底缓存版本。
 *    - rowSchemas 记录各 store 上一次成功应用的运行时 row schema。
 *    - 以后可以继续存放其他数据库内部状态。
 */
export const CACHE_STORE_DEFINITIONS = {
    [USER_INFO_STORE_NAME]: {
        name: USER_INFO_STORE_NAME,
        keyPath: 'id',
        // Bumped when the public user fields gained verified; old rows lack the field.
        version: 2,
    },
    // Video fields deliberately have no row schema: upgrades clear this store instead of reading/migrating all rows.
    [VIDEO_INFO_STORE_NAME]: {
        name: VIDEO_INFO_STORE_NAME,
        keyPath: ['scope', 'id'],
        // Bump with frontend releases that change cached video field definitions or semantics.
        version: 2,
        indexes: [{ name: 'scope', keyPath: 'scope' }],
    },
} as const;

type CacheStoreName = keyof typeof CACHE_STORE_DEFINITIONS;
type CacheTransactionMode = 'readonly' | 'readwrite';

type StoreVersionMap = Partial<Record<CacheStoreName, number>>;
type StoreRowSchemaMap = Partial<Record<CacheStoreName, CacheRowSchema>>;

export const CACHE_STORE_SCHEMA_VERSIONS = Object.fromEntries(
    Object.entries(CACHE_STORE_DEFINITIONS).map(([storeName, definition]) => [storeName, definition.version]),
) as Record<CacheStoreName, number>;

export interface SaoleiCacheDB extends DBSchema {
    [META_STORE_NAME]: {
        key: string;
        value: unknown;
    };
    [USER_INFO_STORE_NAME]: {
        key: IDBValidKey;
        value: unknown;
    };
    [VIDEO_INFO_STORE_NAME]: {
        key: [string, number];
        value: unknown;
        indexes: { scope: string };
    };
}

let storeVersionPromise: Promise<void> | null = null;
let storeVersionsChecked = false;
let rowSchemaRevision = 0;
let ensuredRowSchemaRevision = -1;
const registeredRowSchemas: StoreRowSchemaMap = {};

let databasePromise: Promise<IDBPDatabase<SaoleiCacheDB>> | undefined;

function openDatabase(): Promise<IDBPDatabase<SaoleiCacheDB>> {
    databasePromise ??= openDB<SaoleiCacheDB>(CACHE_DB_NAME, CACHE_DB_VERSION, {
        upgrade(db, _oldVersion, _newVersion, tx) {
            if (!db.objectStoreNames.contains(META_STORE_NAME)) {
                db.createObjectStore(META_STORE_NAME);
            }

            getStoreNames().forEach((storeName) => {
                const definition: CacheStoreDefinition = CACHE_STORE_DEFINITIONS[storeName];
                const store = db.objectStoreNames.contains(storeName)
                    ? tx.objectStore(storeName) as unknown as IDBObjectStore
                    : db.createObjectStore(storeName, { keyPath: typeof definition.keyPath === 'string' ? definition.keyPath : [...definition.keyPath] }) as unknown as IDBObjectStore;

                syncStoreIndexes(store, definition);
            });
        },
    });
    return databasePromise;
}

function syncStoreIndexes(store: IDBObjectStore, definition: CacheStoreDefinition) {
    const expectedIndexes = definition.indexes ?? [];

    expectedIndexes.forEach((index) => {
        if (!store.indexNames.contains(index.name)) {
            store.createIndex(index.name, typeof index.keyPath === 'string' ? index.keyPath : [...index.keyPath], index.options);
        }
    });

    Array.from(store.indexNames).forEach((indexName) => {
        if (!expectedIndexes.some((index) => index.name === indexName)) {
            store.deleteIndex(indexName);
        }
    });
}

export async function getTransaction<StoreName extends CacheStoreName, Mode extends CacheTransactionMode>(
    storeName: StoreName,
    mode: Mode,
): Promise<IDBPTransaction<SaoleiCacheDB, [StoreName], Mode>> {
    const db = await getDatabase();
    return db.transaction(storeName, mode);
}

export function registerStoreRowSchema(storeName: CacheStoreName, rowSchema: CacheRowSchema): void {
    registeredRowSchemas[storeName] = rowSchema;
    rowSchemaRevision += 1;
}

export async function getStoreMeta<Value = unknown>(key: string): Promise<Value | undefined> {
    const db = await getDatabase();
    return db.get(META_STORE_NAME, key) as Promise<Value | undefined>;
}

export async function setStoreMeta(key: string, value: unknown): Promise<void> {
    const db = await getDatabase();
    await db.put(META_STORE_NAME, value, key);
}

function getStoreNames() {
    return Object.keys(CACHE_STORE_DEFINITIONS) as CacheStoreName[];
}

async function clearVersionChangedStores(
    db: IDBPDatabase<SaoleiCacheDB>,
    previousVersions: StoreVersionMap,
) {
    const storesToClear = Object.entries(CACHE_STORE_SCHEMA_VERSIONS).filter(
        ([storeName, version]) => previousVersions[storeName as CacheStoreName] !== version,
    );

    await Promise.all(storesToClear.map(async ([storeName]) => {
        const tx = db.transaction(storeName as CacheStoreName, 'readwrite');
        const { store } = tx;

        await store.clear();
        await tx.done;
    }));
    await db.put(META_STORE_NAME, CACHE_STORE_SCHEMA_VERSIONS, STORE_VERSIONS_KEY);
}

function cloneDefaultValue(value: unknown) {
    if (value === undefined || value === null) return value;
    if (typeof structuredClone === 'function') return structuredClone(value);
    if (typeof value !== 'object') return value;
    return JSON.parse(JSON.stringify(value)) as unknown;
}

function convertValue(value: unknown, type: CacheRowColumnType): unknown {
    switch (type) {
        case 'array':
            if (Array.isArray(value)) return value;
            if (typeof value === 'string') {
                const parsed = JSON.parse(value) as unknown;
                if (Array.isArray(parsed)) return parsed;
            }
            throw new Error('Value cannot be converted to array');
        case 'boolean':
            if (typeof value === 'boolean') return value;
            if (typeof value === 'number') return value !== 0;
            if (typeof value === 'string') {
                if (value === 'true' || value === '1') return true;
                if (value === 'false' || value === '0') return false;
            }
            throw new Error('Value cannot be converted to boolean');
        case 'number': {
            const converted = Number(value);
            if (Number.isFinite(converted)) return converted;
            throw new Error('Value cannot be converted to number');
        }
        case 'object':
            if (value !== null && typeof value === 'object' && !Array.isArray(value)) return value;
            if (typeof value === 'string') {
                const parsed = JSON.parse(value) as unknown;
                if (parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed;
            }
            throw new Error('Value cannot be converted to object');
        case 'string':
            return String(value);
        case 'unknown':
            return value;
    }
}

function getObjectValue(row: unknown, key: string) {
    if (row === null || typeof row !== 'object' || Array.isArray(row)) {
        throw new Error('Cached row is not an object');
    }

    return (row as Record<string, unknown>)[key];
}

function hasObjectKey(row: unknown, key: string) {
    return row !== null
        && typeof row === 'object'
        && !Array.isArray(row)
        && Object.prototype.hasOwnProperty.call(row, key);
}

function migrateRow(row: unknown, previousSchema: Partial<CacheRowSchema>, currentSchema: CacheRowSchema) {
    const migrated: Record<string, unknown> = {};

    Object.entries(currentSchema).forEach(([columnName, columnDefinition]) => {
        if (!hasObjectKey(row, columnName)) {
            if (!Object.prototype.hasOwnProperty.call(columnDefinition, 'default')) {
                throw new Error(`Missing default value for new column "${columnName}"`);
            }
            migrated[columnName] = cloneDefaultValue(columnDefinition.default);
            return;
        }

        const value = getObjectValue(row, columnName);
        const previousColumn = previousSchema[columnName];
        migrated[columnName] = previousColumn?.type === columnDefinition.type
            ? value
            : convertValue(value, columnDefinition.type);
    });

    return migrated;
}

function areRowSchemasEqual(previousSchema: CacheRowSchema | undefined, currentSchema: CacheRowSchema) {
    return JSON.stringify(previousSchema ?? {}) === JSON.stringify(currentSchema);
}

async function migrateStoreRows(
    db: IDBPDatabase<SaoleiCacheDB>,
    storeName: CacheStoreName,
    previousSchema: CacheRowSchema,
    currentSchema: CacheRowSchema,
) {
    try {
        const rows = await db.getAll(storeName);
        const migratedRows = rows.map((row) => migrateRow(row, previousSchema, currentSchema));
        const tx = db.transaction(storeName, 'readwrite');
        const { store } = tx;

        await store.clear();
        await Promise.all(migratedRows.map((row) => store.put(row)));
        await tx.done;
    } catch (err) {
        console.warn(`Failed to migrate IndexedDB store "${storeName}", clearing it instead.`, err);
        const clearTx = db.transaction(storeName, 'readwrite');
        const { store } = clearTx;

        await store.clear();
        await clearTx.done;
    }
}

async function ensureRowSchemas(db: IDBPDatabase<SaoleiCacheDB>) {
    const previousSchemaMap = ((await db.get(META_STORE_NAME, ROW_SCHEMAS_KEY)) as StoreRowSchemaMap | undefined) ?? {};
    const schemasToUpdate = Object.entries(registeredRowSchemas).filter(
        ([storeName, currentSchema]) => !areRowSchemasEqual(previousSchemaMap[storeName as CacheStoreName], currentSchema),
    );

    await Promise.all(schemasToUpdate.map(async ([storeName, currentSchema]) => {
        await migrateStoreRows(
            db,
            storeName as CacheStoreName,
            previousSchemaMap[storeName as CacheStoreName] ?? {},
            currentSchema,
        );
    }));

    if (schemasToUpdate.length > 0) {
        await db.put(META_STORE_NAME, { ...previousSchemaMap, ...registeredRowSchemas }, ROW_SCHEMAS_KEY);
    }
}

async function ensureStoreVersions(db: IDBPDatabase<SaoleiCacheDB>) {
    if (storeVersionsChecked && ensuredRowSchemaRevision === rowSchemaRevision) return;
    if (storeVersionPromise) return storeVersionPromise;

    storeVersionPromise = (async () => {
        const targetRowSchemaRevision = rowSchemaRevision;

        if (!storeVersionsChecked) {
            const previousVersions = ((await db.get(META_STORE_NAME, STORE_VERSIONS_KEY)) as StoreVersionMap | undefined) ?? {};
            await clearVersionChangedStores(db, previousVersions);
            storeVersionsChecked = true;
        }

        await ensureRowSchemas(db);
        ensuredRowSchemaRevision = targetRowSchemaRevision;
    })().catch((err: unknown) => {
        throw err;
    }).finally(() => {
        storeVersionPromise = null;
    });

    return storeVersionPromise;
}

export async function getDatabase(): Promise<IDBPDatabase<SaoleiCacheDB>> {
    const db = await openDatabase();
    await ensureStoreVersions(db);
    return db;
}
