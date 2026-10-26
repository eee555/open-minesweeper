from django.db.models import TextChoices


class MS_TextChoices:
    class Mode(TextChoices):
        STD = '00', ('标准')
        UPK = '01', ('upk')
        WQ = '04', ('win7')
        JSW = '05', ('竞速无猜')
        QWC = '06', ('强无猜')
        RWC = '07', ('弱无猜')
        ZWC = '08', ('准无猜')
        QKC = '09', ('强可猜')
        RKC = '10', ('弱可猜')
        BZD = '11', ('标准递归')

    class Level(TextChoices):
        BEGINNER = 'b', ('初级')
        INTERMEDIATE = 'i', ('中级')
        EXPERT = 'e', ('高级')
        CUSTOM_8_8_40 = 'c8_8_40', ('8x8 40雷')
        CUSTOM_16_16_100 = 'c16_16_100', ('16x16 100雷')
        CUSTOM_16_30_150 = 'c16_30_150', ('16x30 150雷')
        CUSTOM_24_30_200 = 'c24_30_200', ('24x30 200雷')

    class State(TextChoices):
        PLAIN = 'a', ('已上传但未审核')
        FROZEN = 'b', ('审核未通过，被冻结')
        OFFICIAL = 'c', ('已通过审核')
        IDENTIFIER = 'd', ('标识不匹配')
        EXTERNAL = 'e', ('外部网站审核')

    class Software(TextChoices):
        AVF = 'a', ('avf')
        EVF = 'e', ('evf')
        MVF = 'm', ('mvf')
        RMV = 'r', ('rmv')


class Saolei_TextChoices:
    class SaoleiVideoState(TextChoices):
        NOTEXIST = 'n', ('不存在')
        PENDING = 'p', ('未审核')
        FROZEN = 'f', ('已冻结')
        OFFICIAL = 'o', ('正常')

    class SaoleiVideoImportState(TextChoices):
        NOTPLANNED = 'n', ('未计划')
        READY = 'r', ('准备就绪')
        QUEUEING = 'q', ('排队中')
        IMPORTING = 'i', ('导入中')
        IMPORTED = 'd', ('已导入')
        FAILED = 'f', ('导入失败')


class Medal_TextChoices:
    class Series(TextChoices):
        BREAKTHROUGH = 'b', ('破境')
        SPEED = 's', ('神速')
        MASTERY = 'm', ('通明')
        FLAGLESS_BREAKTHROUGH = 'bn', ('盲扫破境')
        FLAGLESS_SPEED = 'sn', ('盲扫神速')
        FLAGLESS_MASTERY = 'mn', ('盲扫通明')
        FLAGLESS_PRECISION = 'pn', ('盲扫·精工')
        FLAGGED_PRECISION = 'pf', ('标旗·精工')
        THREE_FLAGLESS_PRECISION = 'tn', ('三阶盲扫·精工')
        THREE_FLAGGED_PRECISION = 'tf', ('三阶标旗·精工')
        REGISTERED = 'r', ('实名在册')
        REVIEWED = 'v', ('录像过审')
        LEVELS = 'l', ('扫雷新秀')
        LEVELS_NF = 'ln', ('盲扫新秀')
        MODES = 'o', ('走马观花')
        SAOLEI = 'a', ('旧迹新篇')
        SHAREHOLDER = 'h', ('原始股东')

    class Kind(TextChoices):
        PB = 'p', ('pb')
        COMPOSITE = 'c', ('composite')
        ONCE = 'o', ('once')
        COUNT = 'n', ('count')
        BV_SET = 'b', ('bv_set')
        CELL_MASK = 'k', ('cell_mask')
        EVENT_PLACE = 'e', ('event_place')
        GSC_STAT = 's', ('gsc_stat')
        GSC_PLACE = 'g', ('gsc_place')
        MANUAL = 'm', ('manual')
        MIN_VIDEO_ID = 'i', ('min_video_id')

    class Direction(TextChoices):
        ASC = 'a', ('asc')
        DESC = 'd', ('desc')

    class Level(TextChoices):
        BEGINNER = 'b', ('b')
        INTERMEDIATE = 'i', ('i')
        EXPERT = 'e', ('e')

    class Style(TextChoices):
        ANY = 'a', ('any')
        NF = 'n', ('nf')
        FL = 'f', ('fl')


class Tournament_TextChoices:
    class Subclass(TextChoices):
        GSC = 'g', ('GSC比赛')
        WEEKLY = 'w', ('周赛')

    class State(TextChoices):
        PENDING = 'p', ('审核中')
        NORMAL = 'n', ('正常')
        CANCELLED = 'c', ('已取消')
        AWARDED = 'a', ('已颁奖')

    class WeeklyFormat(TextChoices):
        CLASSIC = 'c', ('2高5中')
