from django.dispatch import Signal


# Batch updates bypass model save signals. Send within the mutation transaction
# with the affected player_ids; receivers defer their work until commit.
# Optional video_ids name the changed videos and require a single player.
# lost_qualification must be explicitly True or False; when True, lost_levels
# must list the levels of those videos. Otherwise receivers treat the change as
# unknown and rebuild fully.
videos_bulk_changed = Signal()

# Send after switching storage within the same transaction, with video_id and
# size_delta. Receivers update database statistics before the transaction commits.
video_storage_changed = Signal()
