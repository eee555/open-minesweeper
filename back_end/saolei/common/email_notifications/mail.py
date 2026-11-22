from email import policy as email_policy
from email.message import EmailMessage as MIMEMessage

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from userprofile.utils import EmailNotificationType
from .messages import MESSAGES


class MultilingualNotificationEmail(EmailMessage):
    """RFC 8255 language messages, transported by the existing Django backend."""

    def __init__(self, notification_type: EmailNotificationType, object_ids: list[int], review_path: str, recipient):
        self.notification_type = notification_type
        self.object_ids = object_ids
        self.review_url = f'{settings.EMAIL_WEBSITE_URL}/#{review_path}'
        self.settings_url = f'{settings.EMAIL_WEBSITE_URL}/#/player/{recipient.pk}/settings'
        preface = '\n\n'.join(text['intro'] for text in MESSAGES.values())
        super().__init__(
            subject='待办通知 / Review notification / Notificación de revisión', body=preface,
            from_email=settings.DEFAULT_FROM_EMAIL, to=[recipient.email],
        )

    def message(self, *, policy=email_policy.default):
        message = super().message(policy=policy)
        message.make_mixed()
        message.set_type('multipart/multilingual')
        message['Content-Disposition'] = 'inline'
        for language, text in MESSAGES.items():
            title = text[self.notification_type]
            context = {
                'language': language, 'title': title, 'object_ids': self.object_ids[:20],
                'count': len(self.object_ids), 'objects_label': text['objects'],
                'review_label': text['review'], 'review_url': self.review_url,
                'settings_label': text['settings'], 'settings_url': self.settings_url,
            }
            content = MIMEMessage(policy=policy)
            content['Subject'] = title
            content['From'] = self.from_email
            content['To'] = self.to[0]
            identifiers = ', '.join(f'#{object_id}' for object_id in self.object_ids[:20])
            content.set_content(
                f'{title}\n\n{text["objects"]}: {len(self.object_ids)}\n{identifiers}\n\n'
                f'{text["review"]}: {self.review_url}\n{text["settings"]}: {self.settings_url}\n',
                charset='utf-8',
            )
            content.add_alternative(render_to_string('common/email_notification.html', context), subtype='html', charset='utf-8')
            part = MIMEMessage(policy=policy)
            part.set_content(content)
            part['Content-Language'] = language
            part['Content-Translation-Type'] = 'human'
            part['Content-Disposition'] = 'inline'
            message.attach(part)
        return message
