from django.tasks import task

from .files import original_file
from .models import VideoModel
from .utils import calculate_pluck, is_custom_pluck_video, normalize_pluck


def helper_video_pluck(video: VideoModel):
    if is_custom_pluck_video(video):
        task_video_pluck.enqueue(video.id)


@task(priority=-1)
def task_video_pluck(video_id: int):
    video = VideoModel.objects.get(id=video_id)
    with original_file(video.file.name, video.compression_format, video.original_filename) as replay:
        pluck = normalize_pluck(calculate_pluck(replay.name, replay.read()))
    video.pluck = pluck
    video.save(update_fields=['pluck'])
