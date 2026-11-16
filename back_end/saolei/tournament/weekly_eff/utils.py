WEEKLY_EFF_DEFAULT_SCORE = 780.0
WEEKLY_EFF_BEST_FIELDS = ['weekly_eff_best', 'weekly_eff_best_year', 'weekly_eff_best_week']


def default_weekly_eff_et():
    return [(0, 240.0), (0, 240.0)]


def default_weekly_eff_it():
    return [(0, 60.0) for _ in range(5)]
