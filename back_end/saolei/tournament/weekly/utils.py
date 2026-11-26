from config.text_choices import MS_TextChoices, Tournament_TextChoices

WEEKLY_SCORE_CATEGORIES = {
    Tournament_TextChoices.WeeklyFormat.CLASSIC: 'weekly_classic',
    Tournament_TextChoices.WeeklyFormat.NF: 'weekly_nf',
    Tournament_TextChoices.WeeklyFormat.QWC: 'weekly_qwc',
    Tournament_TextChoices.WeeklyFormat.QWC_NF: 'weekly_qwc_nf',
}
WEEKLY_TOTAL_FIELDS = tuple(f'{category}_total' for category in WEEKLY_SCORE_CATEGORIES.values())
WEEKLY_BEST_FIELDS = tuple(f'{category}_best' for category in WEEKLY_SCORE_CATEGORIES.values())
WEEKLY_FORMAT_NAMES = {
    Tournament_TextChoices.WeeklyFormat.CLASSIC: {'zh': '经典', 'en': 'Classic', 'es': 'Clásico'},
    Tournament_TextChoices.WeeklyFormat.NF: {'zh': 'NF', 'en': 'NF', 'es': 'NF'},
    Tournament_TextChoices.WeeklyFormat.QWC: {'zh': '强无猜', 'en': 'Hardcore NG', 'es': 'Sin adivinar estricto'},
    Tournament_TextChoices.WeeklyFormat.QWC_NF: {'zh': '强无猜NF', 'en': 'Hardcore NG NF', 'es': 'Sin adivinar estricto NF'},
}


def weekly_video_filters(tournament_format):
    tournament_format = Tournament_TextChoices.WeeklyFormat(tournament_format)
    mode = MS_TextChoices.Mode.QWC if tournament_format in (Tournament_TextChoices.WeeklyFormat.QWC, Tournament_TextChoices.WeeklyFormat.QWC_NF) else MS_TextChoices.Mode.STD
    filters = {'mode': mode}
    if tournament_format in (Tournament_TextChoices.WeeklyFormat.NF, Tournament_TextChoices.WeeklyFormat.QWC_NF):
        filters['right_ce'] = 0
    return filters


def weekly_encode_best(score: int, year: int, week: int):
    return score * 100000 + (year % 1000) * 100 + week
