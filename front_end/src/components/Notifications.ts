import type { AxiosResponse } from 'axios';
import { isAxiosError } from 'axios';
import { ElNotification } from 'element-plus';

import i18n from '@/i18n';
import { local } from '@/store/local';

const { t } = i18n.global;

const notificationMessage: Record<number, string> = {
    200: 'response.OK',
    400: 'response.BadRequest',
    403: 'response.Forbidden',
    404: 'response.NotFound',
    413: 'response.PayloadTooLarge',
    415: 'response.UnsupportedMediaType',
    429: 'response.TooManyRequests',
    500: 'response.InternalServerError',
};

export function baseErrorNotification(title: string, message: string): void {
    ElNotification({
        title: title,
        message: message,
        type: 'error',
        duration: local.value.notification_duration,
    });
}

export function httpErrorNotification(error: unknown): void {
    if (isRankingRefreshError(error)) {
        baseErrorNotification(t('msg.actionFail'), t('ranking.refreshBusy'));
        return;
    }
    const status = isAxiosError(error) ? error.response?.status : undefined;
    if (status !== undefined && status in notificationMessage) {
        baseErrorNotification(t('msg.actionFail'), t(notificationMessage[status]));
    } else {
        unknownErrorNotification(error);
    }
}

export function isRankingRefreshError(error: unknown): boolean {
    return isAxiosError<{ object?: string; category?: string }>(error) && error.response?.status === 503 && error.response.data?.object === 'top' && error.response.data?.category === 'refreshing';
}

export function actionSuccessNotification(): void {
    ElNotification({
        title: t('msg.actionSuccess'),
        type: 'success',
        duration: local.value.notification_duration,
    });
}

export function successNotification(response: AxiosResponse): void {
    if (response.status === 200) {
        actionSuccessNotification();
    } else {
        unknownErrorNotification(response);
    }
}

export function unknownErrorNotification(error: unknown): void {
    baseErrorNotification(t('msg.unknownError'), String(error));
}

export function generalErrorNotification(object: string, category: string): void {
    baseErrorNotification(t(`errorMsg.${object}.title`), t(`errorMsg.${object}.${category}`));
}
