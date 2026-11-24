from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from userprofile.utils import EmailNotificationType
from .messages import MESSAGES


class NotificationEmail(EmailMultiAlternatives):
    """Plain text and HTML in the recipient's saved language."""

    def __init__(self, notification_type: EmailNotificationType, object_ids: list[int], review_path: str, recipient):
        language = recipient.language
        text = MESSAGES[language]
        title = text[notification_type]
        review_url = f'{settings.EMAIL_WEBSITE_URL}/#{review_path}'
        settings_url = f'{settings.EMAIL_WEBSITE_URL}/#/player/{recipient.pk}/settings'
        context = {
            'language': language, 'title': title, 'object_ids': object_ids[:20],
            'count': len(object_ids), 'objects_label': text['objects'],
            'review_label': text['review'], 'review_url': review_url,
            'settings_label': text['settings'], 'settings_url': settings_url,
        }
        identifiers = ', '.join(f'#{object_id}' for object_id in object_ids[:20])
        body = (
            f'{title}\n\n{text["objects"]}: {len(object_ids)}\n{identifiers}\n\n'
            f'{text["review"]}: {review_url}\n{text["settings"]}: {settings_url}\n'
        )
        super().__init__(
            subject=title, body=body, from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient.email], headers={'Content-Language': language},
        )
        self.attach_alternative(render_to_string('common/email_notification.html', context), 'text/html')
