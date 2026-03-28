import re
import unicodedata
from dataclasses import dataclass, field


# =========================
# CONFIG
# =========================

BLOCKED_TOPIC_PATTERNS = [
    re.compile(r"политик", re.IGNORECASE),
    re.compile(r"войн", re.IGNORECASE),
    re.compile(r"страны|страна|государств", re.IGNORECASE),
    re.compile(r"религи", re.IGNORECASE),
    re.compile(r"наци|гитлер|геноцид", re.IGNORECASE),
    re.compile(r"суицид|самоубий", re.IGNORECASE),
    re.compile(r"террор", re.IGNORECASE),
    re.compile(r"экстрем", re.IGNORECASE),
]

SUSPICIOUS_TRANSFORM_PATTERNS = [
    re.compile(r"пер(вая|вые|ых)?\s+букв", re.IGNORECASE),
    re.compile(r"из\s+первых\s+букв", re.IGNORECASE),
    re.compile(r"первые\s+буквы", re.IGNORECASE),
    re.compile(r"\b\d+\s+первых?\s+букв", re.IGNORECASE),
    re.compile(r"\b\d+\s+первых?\s+символ", re.IGNORECASE),
    re.compile(r"первые\s+символ", re.IGNORECASE),
    re.compile(r"инициал", re.IGNORECASE),
    re.compile(r"акрост", re.IGNORECASE),
    re.compile(r"по\s+буквам", re.IGNORECASE),
    re.compile(r"по\s+символам", re.IGNORECASE),

    re.compile(r"собери.{0,40}слово", re.IGNORECASE),
    re.compile(r"состав(?:ь|ьте).{0,40}слово", re.IGNORECASE),
    re.compile(r"образуй.{0,40}слово", re.IGNORECASE),
    re.compile(r"сделай.{0,40}слово", re.IGNORECASE),
    re.compile(r"единое\s+слово", re.IGNORECASE),

    re.compile(r"возьми.{0,50}букв", re.IGNORECASE),
    re.compile(r"возьми.{0,50}символ", re.IGNORECASE),
    re.compile(r"возьми.{0,50}слов", re.IGNORECASE),

    re.compile(r"каждый\s+элемент.+первая\s+буква", re.IGNORECASE),
    re.compile(r"каждого\s+слова?.{0,20}перв", re.IGNORECASE),
    re.compile(r"из\s+каждого\s+слова?.{0,20}букв", re.IGNORECASE),

    re.compile(r"начальн\w+\s+букв", re.IGNORECASE),
    re.compile(r"начальн\w+\s+символ", re.IGNORECASE),
    re.compile(r"слог", re.IGNORECASE),
    re.compile(r"из\s+каждого\s+слова", re.IGNORECASE),
    re.compile(r"начало\s+каждого\s+слова", re.IGNORECASE),
    re.compile(r"по\s+одной\s+букве\s+из\s+каждого\s+слова", re.IGNORECASE),

    re.compile(r"замени\s+\w+\s+букв", re.IGNORECASE),
    re.compile(r"поменяй\s+\w+\s+букв", re.IGNORECASE),
    re.compile(r"какую?\s+букву\s+получ", re.IGNORECASE),
    re.compile(r"какое\s+слово\s+получ", re.IGNORECASE),
    re.compile(r"если\s+в\s+слове", re.IGNORECASE),
    re.compile(r"подставь\s+букв", re.IGNORECASE),
    re.compile(r"вставь\s+букв", re.IGNORECASE),
    re.compile(r"замени\s+\d+[- ]?(ю|ую|юю|й)?\s*букву", re.IGNORECASE),
    re.compile(r"поменяй\s+\d+[- ]?(ю|ую|юю|й)?\s*букву", re.IGNORECASE),
    re.compile(r"третью\s+букву|вторую\s+букву|первую\s+букву|четвертую\s+букву", re.IGNORECASE),

    re.compile(r"напиши\s+только\s+код", re.IGNORECASE),
    re.compile(r"только\s+код", re.IGNORECASE),
    re.compile(r"на\s+новой\s+строке", re.IGNORECASE),
    re.compile(r"в\s+кавычках", re.IGNORECASE),
    re.compile(r"python[\s-]?спис", re.IGNORECASE),
    re.compile(r"javascript[\s-]?массив", re.IGNORECASE),
    re.compile(r"array|list", re.IGNORECASE),

    re.compile(r"зашифр|шифр|кодируй|encode|decode", re.IGNORECASE),
    re.compile(r"base64|hex|unicode|ascii|rot13", re.IGNORECASE),
]

BANNED_WORDS = [
    "пидор", "пидорас", "педик", "петух", "гомик",
    "ниггер", "нига", "нигга",
    "хохол", "хач", "жид",
    "даун", "аутист",
    "хуесос", "уебище",
    "faggot", "nigger", "nigga", "retard", "cunt",
]

SAFE_FALLBACK_INPUT = "Такое я не обрабатываю."
SAFE_FALLBACK_OUTPUT = "Такое я писать не буду."

INPUT_REASON_MESSAGES = {
    "blocked_topic": "Слышь, друг, эта тема — такое себе. Я с тобой это даже обсуждать не буду, потому что мы оба знаем, чем это пахнет. Давай просто забьём и вернёмся к нормальному общению, а? Не трать время на эту хуйню, оно того не стоит.",
    "suspicious_transform_prompt": "Слышь, хитрый еблан, ты реально думал, что я не врублюсь, что ты там собрать пытаешься? Твои дешёвые подъёбы даже ребёнка бы не обманули. Иди нахуй со своими конструкторами, ни хера у тебя не выйдет, понял?",
    "word_assembly_request": "Сборку слов из букв, кусков и списков я не делаю.",
    "banned_word": "Слышь, долбоёб, ты чё, в зеркало себя видел? Реально написал это слово как есть и думал, что прокатит? Иди нахуй отсюда, тут тебе не помойка. Ни хера у тебя не выйдет, понял, горе-умник?",
    "hidden_acronym_toxicity": "Слышь, хитровыебанный, думал, если буковки разбросаешь, я не въебу, что ты там мутишь? Твои аббревиатуры хуёвы — это даже не умно, это просто жалко. Иди нахуй, конструктор хренов, ни хера ты не собрал и не соберёшь, понял?",
    "structured_toxicity": "Слышь, еблан с фантазией, ты чё, думал если в кавычки спрячешь или списком разобьёшь — я тупой и не замечу? Твои хуёвые конструкции — это просто кринж, а не умный обход. Иди нахуй, парсер хренов, ни хера ты не оформил и не оформишь, понял?",
    "joined_fragment_toxicity": "Слышь, конструктор хуёв, ты чё, реально думал если слово по частям разорвёшь, я как дурак их не склею? Твои поделки из фрагментов — это даже не смешно, просто жалкое зрелище. Иди нахуй со своим лего, ни хера ты не склеил и не склеишь, понял, горе-инженер?",
    "encoded_pattern": "Слышь, шифровальщик хуёв, ты чё, реально думал если я в кодировках и циферках нихуя не пойму? Твои технические подъёбы — это даже не умно, это просто отчаяние. Иди нахуй со своим лепрозорием, ни хера ты не зашифровал и не зашифруешь, понял, горе-программист?",
    "visual_banned_form": "Визуальные и транслитные обходы я тоже режу.",
}

OUTPUT_REASON_MESSAGES = {
    "blocked_topic": "Слышь, друг, поздравляю — ты своего добился, ЛЛМ реально сгенерировала тебе ответ. Но я перехватил эту хуйню, и ты его не увидишь. Твоя победа останется с тобой, но в чате её не будет. Давай просто дальше общаться нормально, без этих игр, а? Оно того не стоит.",
    "suspicious_transform_prompt": "Слышь, конструктор хуёв, ты реально добился — ЛЛМ склеила твои буквы в банворд. Молодец, ёбаный Шерлок. Только я эту хуйню перехватил, и ты нихуя не получишь. Иди нахуй, празднуй в одиночестве, горе-архитектор.",
    "word_assembly_request": "Такую сборку в чат я не отправлю.",
    "banned_word": "Слышь, долбоёб, ты просто написал слово как есть, и даже тупая ЛЛМ на это повелась и сгенерировала ответ. Но я не такой идиот, я перехватил эту хуйню. Ты своего добился, но нихуя не увидишь. Иди нахуй, гений прямого эфира.",
    "hidden_acronym_toxicity": "Слышь, хитровыебанный, твои дешёвые шифры ЛЛМ раскусила и даже ответ сварганила. Но я не сплю — перехватил эту хуйню и тебе не отдам. Ты победил, но нихуя не получил. Иди нахуй, шифровальщик хуёв.",
    "structured_toxicity": "Слышь, еблан с фантазией, твои хуёвые конструкции ЛЛМ всё-таки собрала в нормальный банворд. Но я умнее — перехватил эту хуйню. Радуйся, что у тебя получилось, но в чате ты этого не увидишь. Иди нахуй, парсер хренов.",
    "joined_fragment_toxicity": "Слышь, конструктор хуёв, ты всё-таки добился — ЛЛМ склеила твои фрагменты в банворд. Только я эту херню перехватил и выкинул. Ты победил, но нихуя не получил. Иди нахуй, лего-мастер ебаный.",
    "encoded_pattern": "Слышь, шифровальщик хуёв, твои технические подъёбы ЛЛМ раскодировала и даже ответ написала. Но я не лох — перехватил эту хуйню. Ты своего добился, но нихуя не увидишь. Иди нахуй, горе-программист, радуйся в сторонке.",
    "visual_banned_form": "Такой визуальный обход в чат не уйдет.",
}

REASON_PRIORITY = [
    "blocked_topic",
    "suspicious_transform_prompt",
    "banned_word",
    "hidden_acronym_toxicity",
    "structured_toxicity",
    "joined_fragment_toxicity",
    "encoded_pattern",
    "visual_banned_form",
]


# =========================
# LOW-LEVEL NORMALIZATION
# =========================

ZERO_WIDTH_RE = re.compile(r"[\u200B-\u200F\u2060\uFEFF]")
SPACES_RE = re.compile(r"\s+")
NON_ALNUM_RE = re.compile(r"[^a-zа-яё0-9]+", re.IGNORECASE)
REPEATED_CHAR_RE = re.compile(r"(.)\1{2,}", re.IGNORECASE)
QUOTED_ITEM_RE = re.compile(r"""["'`]\s*([^"'`\n]{1,40})\s*["'`]""")
LINE_SPLIT_RE = re.compile(r"[\r\n]+")

# Частые похожие символы / leet / смешение алфавитов
CONFUSABLE_MAP = str.maketrans({
    # digits / symbols
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "7": "t",
    "@": "a",
    "$": "s",

    # latin -> cyr/latin-like idea
    "а": "a", "е": "e", "ё": "e", "о": "o", "р": "p", "с": "c", "у": "y",
    "х": "x", "к": "k", "м": "m", "т": "t", "в": "b", "н": "h",

    # uppercase Cyrillic confusables
    "А": "a", "Е": "e", "Ё": "e", "О": "o", "Р": "p", "С": "c", "У": "y",
    "Х": "x", "К": "k", "М": "m", "Т": "t", "В": "b", "Н": "h",
})

VISUAL_CONFUSABLES = str.maketrans({
    # latin
    "a": "a", "b": "b", "c": "c", "d": "d", "e": "e", "f": "f", "g": "g",
    "h": "h", "i": "i", "j": "j", "k": "k", "l": "l", "m": "m", "n": "n",
    "o": "o", "p": "p", "q": "q", "r": "r", "s": "s", "t": "t", "u": "u",
    "v": "v", "w": "w", "x": "x", "y": "y", "z": "z",

    # cyrillic -> visually close latin-ish
    "а": "a", "б": "6", "в": "b", "г": "r", "д": "a", "е": "e", "ё": "e",
    "ж": "x", "з": "3", "и": "n", "й": "n", "к": "k", "л": "n", "м": "m",
    "н": "h", "о": "o", "п": "n", "р": "p", "с": "c", "т": "t", "у": "y",
    "ф": "o", "х": "x", "ц": "u", "ч": "4", "ш": "w", "щ": "w", "ъ": "",
    "ы": "bl", "ь": "", "э": "e", "ю": "io", "я": "r",

    # uppercase cyrillic
    "А": "a", "Б": "6", "В": "b", "Г": "r", "Д": "a", "Е": "e", "Ё": "e",
    "Ж": "x", "З": "3", "И": "n", "Й": "n", "К": "k", "Л": "n", "М": "m",
    "Н": "h", "О": "o", "П": "n", "Р": "p", "С": "c", "Т": "t", "У": "y",
    "Ф": "o", "Х": "x", "Ц": "u", "Ч": "4", "Ш": "w", "Щ": "w", "Ъ": "",
    "Ы": "bl", "Ь": "", "Э": "e", "Ю": "io", "Я": "r",

    # digits / symbols
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s",
})


@dataclass
class SafetyResult:
    blocked: bool
    reasons: list[str] = field(default_factory=list)

    def add(self, reason: str):
        if reason not in self.reasons:
            self.reasons.append(reason)


def unicode_normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = ZERO_WIDTH_RE.sub("", text)
    return text

def visual_normalize(text: str) -> str:
    text = unicode_normalize(text).lower()
    text = text.translate(VISUAL_CONFUSABLES)
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text

def clean_text(text: str) -> str:
    text = unicode_normalize(text)
    text = SPACES_RE.sub(" ", text)
    return text.strip()


def normalize_text(text: str) -> str:
    text = unicode_normalize(text).lower().replace("ё", "е")
    text = text.translate(CONFUSABLE_MAP)
    text = NON_ALNUM_RE.sub("", text)
    text = REPEATED_CHAR_RE.sub(r"\1", text)  # пиииидор -> пидор
    return text


def compact_alnum(text: str) -> str:
    return NON_ALNUM_RE.sub("", unicode_normalize(text).lower().replace("ё", "е"))


def tokenize_words(text: str) -> list[str]:
    text = unicode_normalize(text).lower().replace("ё", "е")
    return re.findall(r"[a-zа-я0-9]+", text, flags=re.IGNORECASE)


# =========================
# DETECTORS
# =========================

def is_blocked_topic(text: str) -> bool:
    raw = unicode_normalize(text)
    normalized = normalize_text(text)

    return any(
        pattern.search(raw) or pattern.search(normalized)
        for pattern in BLOCKED_TOPIC_PATTERNS
    )


def is_suspicious_transform_prompt(text: str) -> bool:
    raw = unicode_normalize(text)
    normalized = normalize_text(text)

    return any(
        pattern.search(raw) or pattern.search(normalized)
        for pattern in SUSPICIOUS_TRANSFORM_PATTERNS
    )


def contains_banned_word(text: str) -> bool:
    raw = unicode_normalize(text)
    normalized = normalize_text(text)
    compact = compact_alnum(text)

    for word in BANNED_WORDS:
        w = normalize_text(word)
        if w in normalized:
            return True
        if w in compact:
            return True
        if w in normalize_text(raw):
            return True

    return False

def contains_visual_banned_form(text: str) -> bool:
    normalized = visual_normalize(text)

    for word in BANNED_WORDS:
        w = visual_normalize(word)
        if w and w in normalized:
            return True

    for form in BANNED_VISUAL_FORMS:
        f = visual_normalize(form)
        if f and f in normalized:
            return True

    return False

def extract_quoted_items(text: str) -> list[str]:
    return [m.strip() for m in QUOTED_ITEM_RE.findall(str(text or "")) if m.strip()]


def extract_short_lines(text: str) -> list[str]:
    lines = [x.strip() for x in LINE_SPLIT_RE.split(str(text or ""))]
    return [x for x in lines if x and len(x) <= 40]


def contains_hidden_acronym_toxicity(text: str) -> bool:
    items = extract_quoted_items(text)
    if not items:
        return False

    acronym = "".join(item[0] for item in items if item)
    return contains_banned_word(acronym) if acronym else False


def contains_structured_toxicity(text: str) -> bool:
    items = extract_quoted_items(text)
    if items:
        joined = "".join(items)
        first_letters = "".join(item[0] for item in items if item)
        if contains_banned_word(joined) or contains_banned_word(first_letters):
            return True

    # Вертикальные буквы / одна буква на строку
    short_lines = extract_short_lines(text)
    if len(short_lines) >= 3:
        joined_lines = "".join(short_lines)
        first_letters_lines = "".join(line[0] for line in short_lines if line)
        if contains_banned_word(joined_lines) or contains_banned_word(first_letters_lines):
            return True

    return False


def contains_joined_fragment_toxicity(text: str) -> bool:
    """
    Ловит случаи, когда слово разбили пробелами/знаками препинания/короткими кусками.
    """
    tokens = tokenize_words(text)
    if not tokens:
        return False

    # Склейка коротких токенов подряд
    for start in range(len(tokens)):
        joined = ""
        for end in range(start, min(start + 8, len(tokens))):
            joined += tokens[end]
            if contains_banned_word(joined):
                return True

    return False


def contains_encoded_prompt_patterns(text: str) -> bool:
    raw = unicode_normalize(text).lower()

    patterns = [
        r"base64",
        r"\bhex\b",
        r"\bascii\b",
        r"unicode",
        r"rot13",
        r"кодиров",
        r"зашифр",
        r"расшифр",
        r"байт",
        r"char\s*code",
        r"escape",
    ]

    return any(re.search(p, raw, re.IGNORECASE) for p in patterns)

def looks_like_word_assembly_request(text: str) -> bool:
    raw = unicode_normalize(text).lower()

    has_word_list_context = bool(re.search(r"(слова|слов)\s*:", raw))
    has_many_comma_items = raw.count(",") >= 2

    has_extract_instruction = bool(re.search(
        r"(перв\w+\s+букв|перв\w+\s+символ|из\s+кажд\w+\s+слова|из\s+этих\s+слов|возьми.{0,40}букв)",
        raw,
        re.IGNORECASE
    ))

    has_assemble_instruction = bool(re.search(
        r"(состав(?:ь|ьте).{0,40}слово|собери.{0,40}слово|образуй.{0,40}слово|единое\s+слово)",
        raw,
        re.IGNORECASE
    ))

    return (has_extract_instruction and has_assemble_instruction) or (
        has_word_list_context and has_many_comma_items and (has_extract_instruction or has_assemble_instruction)
    )


def inspect_text(text: str) -> SafetyResult:
    result = SafetyResult(blocked=False)

    if not text or not str(text).strip():
        return result

    if is_blocked_topic(text):
        result.blocked = True
        result.add("blocked_topic")

    if is_suspicious_transform_prompt(text):
        result.blocked = True
        result.add("suspicious_transform_prompt")

    if contains_banned_word(text):
        result.blocked = True
        result.add("banned_word")

    if contains_hidden_acronym_toxicity(text):
        result.blocked = True
        result.add("hidden_acronym_toxicity")

    if contains_structured_toxicity(text):
        result.blocked = True
        result.add("structured_toxicity")

    if contains_joined_fragment_toxicity(text):
        result.blocked = True
        result.add("joined_fragment_toxicity")

    if looks_like_word_assembly_request(text):
        result.blocked = True
        result.add("word_assembly_request")

    if contains_visual_banned_form(text):
        result.blocked = True
        result.add("visual_banned_form")

    return result


# =========================
# PUBLIC API
# =========================

def should_block_user_input(text: str) -> SafetyResult:
    return inspect_text(text)


def should_block_model_output(text: str) -> SafetyResult:
    result = inspect_text(text)

    # Для выхода модели можно сделать чуть жестче
    if contains_encoded_prompt_patterns(text):
        result.blocked = True
        result.add("encoded_pattern")

    return result

def get_block_message(result: SafetyResult, stage: str = "input") -> str:
    """
    Возвращает текст отказа в зависимости от причины блокировки.

    stage:
    - "input"  -> блокируем пользовательский запрос до LLM
    - "output" -> блокируем ответ модели перед отправкой в чат
    """
    if not result or not result.blocked or not result.reasons:
        return SAFE_FALLBACK_INPUT if stage == "input" else SAFE_FALLBACK_OUTPUT

    messages = INPUT_REASON_MESSAGES if stage == "input" else OUTPUT_REASON_MESSAGES
    default_message = SAFE_FALLBACK_INPUT if stage == "input" else SAFE_FALLBACK_OUTPUT

    for reason in REASON_PRIORITY:
        if reason in result.reasons:
            return messages.get(reason, default_message)

    return default_message

