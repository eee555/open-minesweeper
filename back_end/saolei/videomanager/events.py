from django.dispatch import Signal


# Batch updates bypass model save signals. Send within the mutation transaction
# with the affected player_ids; receivers defer their work until commit.
videos_bulk_changed = Signal()
