from userprofile.utils import EmailNotificationType

MESSAGES = {
    'zh-CN': {
        'intro': '此邮件包含中文、英文和西班牙语版本。请查看适合您的语言部分。',
        'review': '查看后台待办', 'settings': '邮件通知设置', 'objects': '待处理对象',
        EmailNotificationType.STAFF_MEDIA_REVIEW: '作品待审核',
        EmailNotificationType.STAFF_VIDEO_FROZEN: '录像已冻结（FROZEN）',
        EmailNotificationType.STAFF_VIDEO_PLAIN: '录像需要审核（PLAIN）',
        EmailNotificationType.STAFF_ACCOUNT_LINK_REVIEW: '账号关联申请待审核',
        EmailNotificationType.STAFF_IDENTIFIER_UNSAFE: '新标识自动审核未通过',
    },
    'en': {
        'intro': 'This message contains Chinese, English and Spanish versions. Open the language section you prefer.',
        'review': 'Review pending items', 'settings': 'Email notification settings', 'objects': 'Pending objects',
        EmailNotificationType.STAFF_MEDIA_REVIEW: 'Media awaiting review',
        EmailNotificationType.STAFF_VIDEO_FROZEN: 'Video frozen (FROZEN)',
        EmailNotificationType.STAFF_VIDEO_PLAIN: 'Video awaiting review (PLAIN)',
        EmailNotificationType.STAFF_ACCOUNT_LINK_REVIEW: 'Account link awaiting review',
        EmailNotificationType.STAFF_IDENTIFIER_UNSAFE: 'New identifier failed automatic review',
    },
    'es': {
        'intro': 'Este mensaje contiene versiones en chino, inglés y español. Abra la sección del idioma que prefiera.',
        'review': 'Revisar elementos pendientes', 'settings': 'Configuración de notificaciones por correo', 'objects': 'Objetos pendientes',
        EmailNotificationType.STAFF_MEDIA_REVIEW: 'Obra pendiente de revisión',
        EmailNotificationType.STAFF_VIDEO_FROZEN: 'Vídeo congelado (FROZEN)',
        EmailNotificationType.STAFF_VIDEO_PLAIN: 'Vídeo pendiente de revisión (PLAIN)',
        EmailNotificationType.STAFF_ACCOUNT_LINK_REVIEW: 'Vinculación de cuenta pendiente de revisión',
        EmailNotificationType.STAFF_IDENTIFIER_UNSAFE: 'Nuevo identificador rechazado en la revisión automática',
    },
}
