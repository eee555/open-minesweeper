from userprofile.utils import EmailNotificationType

MESSAGES = {
    'zh-cn': {
        'review': '查看后台待办', 'settings': '邮件通知设置', 'objects': '待处理对象',
        EmailNotificationType.STAFF_MEDIA_REVIEW: '作品待审核',
        EmailNotificationType.STAFF_VIDEO_FROZEN: '录像已冻结',
        EmailNotificationType.STAFF_VIDEO_PLAIN: '录像需要审核',
        EmailNotificationType.STAFF_ACCOUNT_LINK_REVIEW: '账号关联申请待审核',
        EmailNotificationType.STAFF_IDENTIFIER_UNSAFE: '新标识自动审核未通过',
    },
    'en': {
        'review': 'Review pending items', 'settings': 'Email notification settings', 'objects': 'Pending objects',
        EmailNotificationType.STAFF_MEDIA_REVIEW: 'Media awaiting review',
        EmailNotificationType.STAFF_VIDEO_FROZEN: 'Video frozen',
        EmailNotificationType.STAFF_VIDEO_PLAIN: 'Video awaiting review',
        EmailNotificationType.STAFF_ACCOUNT_LINK_REVIEW: 'Account link awaiting review',
        EmailNotificationType.STAFF_IDENTIFIER_UNSAFE: 'New identifier failed automatic review',
    },
    'es': {
        'review': 'Revisar elementos pendientes', 'settings': 'Configuración de notificaciones por correo', 'objects': 'Objetos pendientes',
        EmailNotificationType.STAFF_MEDIA_REVIEW: 'Obra pendiente de revisión',
        EmailNotificationType.STAFF_VIDEO_FROZEN: 'Vídeo congelado',
        EmailNotificationType.STAFF_VIDEO_PLAIN: 'Vídeo pendiente de revisión',
        EmailNotificationType.STAFF_ACCOUNT_LINK_REVIEW: 'Vinculación de cuenta pendiente de revisión',
        EmailNotificationType.STAFF_IDENTIFIER_UNSAFE: 'Nuevo identificador rechazado en la revisión automática',
    },
}
