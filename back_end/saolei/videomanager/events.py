from django.dispatch import Signal


# Batch updates bypass model save signals. Send within the mutation transaction
# with the affected player_ids; receivers defer their work until commit.
videos_bulk_changed = Signal()

# Send after switching storage within the same transaction, with video_id and
# size_delta. Receivers update database statistics before the transaction commits.
video_storage_changed = Signal()
