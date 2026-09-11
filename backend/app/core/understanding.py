"""
Understanding of each buyer turn.

Two interchangeable sources produce the same dict (see `empty_understanding`):
  * LLMUnderstanding: a small, fast Groq model returns structured JSON, so negation and paraphrase are
    handled ("I do not want to book a meeting" is a decline, not a booking).
  * rule_based_understanding: deterministic patterns, used when no LLM key is configured or when the
    model misses the voice latency budget.
The deal-state engine only consumes the dict, so both sources share one merge path.
"""
import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.core.prompts import UNDERSTANDING_EXTRACTION_PROMPT

logger = logging.getLogger("lively.core.understanding")

OBJECTION_TYPES = ("pricing", "competitor", "latency", "trust", "security", "product")
DEMO_REQUESTS = ("request", "accept_proposed", "reschedule", "cancel", "decline")
SENTIMENTS = ("Positive", "Neutral", "Hesitant", "Skeptical", "Frustrated", "Enthusiastic")


def empty_understanding(source: str) -> Dict[str, Any]:
    return {
        "source": source,
        "intent": "other",
        "demo_request": None,
        "requested_time_text": None,
        "slot_choice": None,
        "agrees_to_proposal": False,
        "accepts_previous_answer": False,
        "wants_human": False,
        "legal_or_contract": False,
        "user_count": None,
        "budget": None,
        "timeline": None,
        "role": None,
        "is_decision_maker": None,
        "competitor": None,
        "pain_points": [],
        "objections": [],
        "sentiment": None,
        "email": None,
        "company": None,
    }


# Robust email regex covering standard and spaced speech-to-text tokens
EMAIL_RE = re.compile(r"\b([a-zA-Z0-9._%+-]+)\s*@\s*([a-zA-Z0-9.-]+)\s*\.\s*([a-zA-Z]{2,})\b")
# Spoken emails, e.g. "my email is anish hyd 995 at gmail dot com" or "send to user at company.com"
SPOKEN_EMAIL_RE = re.compile(
    r"(?:(?:my\s+)?e-?mail(?:\s+address)?(?:\s+is|:)?|reach(?:\s+me)?\s+at|send\s+(?:it|the\s+invite|that|to)?\s+to\s*:?|it\'?s\s+)?\s*"
    r"([a-zA-Z0-9][a-zA-Z0-9\s._-]*?)\s+(?:at|@)\s+([a-zA-Z0-9-]+)(?:\s+dot\s+|\.)([a-zA-Z]{2,})\b",
    re.I,
)


def extract_email(text: str) -> Optional[str]:
    if not text:
        return None
    m = EMAIL_RE.search(text)
    if m:
        return f"{m.group(1)}@{m.group(2)}.{m.group(3)}".lower()
    m = SPOKEN_EMAIL_RE.search(text)
    if m:
        raw_user = m.group(1).lower()
        if " dot " in raw_user or "dot" in raw_user.split():
            return None
        user = re.sub(r"\s+", "", raw_user)
        domain = m.group(2).lower().replace(" ", "")
        tld = m.group(3).lower()
        return f"{user}@{domain}.{tld}"
    return None


# ---------------------------------------------------------------- numbers & scale

_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_NUMBER_WORD = "|".join(list(_UNITS) + ["hundred", "thousand"])


def words_to_int(phrase: str) -> Optional[int]:
    total = current = 0
    seen = False
    for token in [t for t in re.split(r"[\s-]+", phrase.lower().strip()) if t]:
        if token == "and":
            continue
        if token == "a":
            current = max(current, 1)
        elif token in _UNITS:
            current += _UNITS[token]
            seen = True
        elif token == "hundred":
            current = max(current, 1) * 100
            seen = True
        elif token == "thousand":
            total += max(current, 1) * 1000
            current = 0
            seen = True
        else:
            return None
    return total + current if seen else None


def parse_count(token: Any) -> Optional[int]:
    if isinstance(token, (int, float)):
        return int(token) if 0 < token < 1_000_000 else None
    if not isinstance(token, str):
        return None
    cleaned = token.replace(",", "").strip()
    if cleaned.isdigit():
        return int(cleaned)
    return words_to_int(cleaned)


_COUNT_TOKEN = rf"(?:\d[\d,]*|(?:{_NUMBER_WORD})(?:[\s-]+(?:{_NUMBER_WORD}|and))*)"
COUNT_RE = re.compile(
    rf"\b({_COUNT_TOKEN})\s+(users|seats|licen[cs]es|agents|reps|sales ?reps|salespeople|people|employees)\b", re.I
)
_PRIMARY_UNITS = {"users", "seats", "licenses", "licences"}


def extract_user_count(lower: str) -> Optional[int]:
    """Latest seat count stated in the turn. Seats/users/licenses win over headcount words."""
    primary, secondary = [], []
    for m in COUNT_RE.finditer(lower):
        value = parse_count(m.group(1))
        if value:
            (primary if m.group(2) in _PRIMARY_UNITS else secondary).append(value)
    if primary:
        return primary[-1]
    return secondary[-1] if secondary else None


# ---------------------------------------------------------------- budget

BUDGET_RE = re.compile(
    r"(\$\s?\d[\d,]*(?:\.\d+)?\s*(?:k|m|million|thousand)?\b(?:\s*(?:arr|a year|per year|annually|/\s*(?:yr|year)))?"
    r"|\b\d[\d,]*(?:\.\d+)?\s*(?:k|thousand|million)\s*(?:dollars|usd)?(?:\s*(?:arr|a year|per year|annually))?)",
    re.I,
)
BUDGET_CONTEXT_RE = re.compile(r"\b(budget|spend|spending|afford|allocated|set aside|up to|approved|arr|annually|per year|a year)\b", re.I)
NO_BUDGET_RE = re.compile(r"\b(?:no|zero|don'?t have (?:a|any)|without a) budget\b", re.I)


def extract_budget(lower: str) -> Optional[str]:
    if NO_BUDGET_RE.search(lower):
        return "No budget allocated"
    if not BUDGET_CONTEXT_RE.search(lower):
        return None  # "$699 a month seems expensive" is a price reaction, not the buyer's budget
    m = BUDGET_RE.search(lower)
    return m.group(1).strip().upper() if m else None


# ---------------------------------------------------------------- authority

_DEPT = r"(?:sales|product|engineering|marketing|operations|revenue|growth|it|technology|finance|customer success|support|partnerships|business development)"
_ROLE = (
    rf"(?:ceo|cto|cfo|coo|cro|cmo|chief \w+ officer|(?:co-?)?founder|owner|president"
    rf"|s?vp(?: of)? {_DEPT}|s?vp|vice president(?: of {_DEPT})?|head of {_DEPT}|director(?: of {_DEPT})?"
    rf"|{_DEPT} manager|project manager|program manager|account manager|manager|team lead"
    rf"|engineer|developer|analyst|consultant|sales rep|intern)"
)
SELF_ROLE_RE = re.compile(
    rf"(?:\bi'?m|\bi am|\bas|\bmy (?:role|title) is|\bi (?:run|lead|head))\s+(?:also\s+|currently\s+|actually\s+|just\s+)?(?:the\s+|a\s+|an\s+|our\s+)?({_ROLE})\b",
    re.I,
)
REPORTS_TO_RE = re.compile(
    rf"(?:report(?:s|ing)? (?:in)?to|my (?:boss|manager) is|work(?:ing)? (?:for|under)|(?:check|clear (?:it|this)|run (?:it|this) by|talk) with"
    rf"|(?:approval|sign-?off|buy-?in) from|(?:it'?s|that'?s|the decision is) (?:up to|with))\s+(?:the\s+|our\s+|my\s+|a\s+)?({_ROLE})\b",
    re.I,
)
DECIDER_RE = re.compile(
    r"\b(?:i (?:decide|make the (?:final )?(?:call|decision)|sign off|approve (?:the )?(?:budget|purchases?|this))"
    r"|(?:it'?s|that'?s) my (?:call|decision)|final (?:call|say) is mine|i have (?:the )?final say|i'?m the decision[- ]maker)\b",
    re.I,
)
NOT_DECIDER_RE = re.compile(r"\b(?:i'?m not the decision[- ]maker|not my (?:call|decision)|i (?:don'?t|do not) (?:decide|make the (?:final )?(?:call|decision)))\b", re.I)
_DECISION_ROLE_PREFIXES = ("ceo", "cto", "cfo", "coo", "cro", "cmo", "chief", "founder", "co-founder", "cofounder", "owner", "president", "vp", "svp", "vice president", "head of", "director")
_ACRONYMS = {"ceo", "cto", "cfo", "coo", "cro", "cmo", "vp", "svp", "it"}


def format_role(role: str) -> str:
    words = []
    for w in role.strip().split():
        lw = w.lower()
        words.append(lw.upper() if lw in _ACRONYMS else lw if lw == "of" else lw.capitalize())
    return " ".join(words)


def extract_authority(lower: str) -> Tuple[Optional[str], Optional[bool]]:
    role: Optional[str] = None
    decision_maker: Optional[bool] = None
    self_role = SELF_ROLE_RE.search(lower)
    reports = REPORTS_TO_RE.search(lower)
    if self_role:
        role = format_role(self_role.group(1))
        decision_maker = self_role.group(1).lower().startswith(_DECISION_ROLE_PREFIXES)
    if reports:
        boss = format_role(reports.group(1))
        role = f"{role} (reports to {boss})" if role else f"Reports to {boss}"
        decision_maker = False
    if DECIDER_RE.search(lower):
        decision_maker = True
    if NOT_DECIDER_RE.search(lower):
        decision_maker = False
    return role, decision_maker


# ---------------------------------------------------------------- timeline & need

_MONTHS = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
TIMELINE_RE = re.compile(
    r"\b(asap|as soon as possible|immediately|right away"
    r"|(?:by|before|within|in|until|end of)\s+(?:the\s+)?(?:next\s+|end of\s+)?(?:\d+|one|two|three|four|five|six|a few|a couple of|few)?\s*(?:days?|weeks?|months?|quarters?|years?)"
    rf"|(?:by|before|in|until|end of)\s+(?:the\s+)?(?:q[1-4]|{_MONTHS})(?:\s+\d{{4}})?"
    r"|(?:this|next)\s+(?:week|month|quarter|year)"
    r"|q[1-4](?:\s+\d{4})?)\b",
    re.I,
)
FORWARD_RE = re.compile(
    r"\b(go live|go-live|live by|launch|roll ?out|rolling out|implement|deploy|deployment|up and running|start using|decide|decision"
    r"|buy|purchase|sign|timeline|timeframe|need (?:it|this|something|a solution)|want (?:it|this)|plan(?:ning)? to|looking to|have (?:it|this) (?:in place|running))\b",
    re.I,
)
MEETING_CONTEXT_RE = re.compile(r"\b(demo|meeting|call|walkthrough|appointment|slot|book|schedule|reschedule)\b", re.I)
_URGENT_PREFIX = ("asap", "as soon as possible", "immediately", "right away", "by ", "before ", "within ")


def extract_timeline(text: str) -> Optional[str]:
    m = TIMELINE_RE.search(text)
    if not m:
        return None
    phrase = m.group(1).strip()
    forward = bool(FORWARD_RE.search(text))
    if not forward and MEETING_CONTEXT_RE.search(text):
        return None  # "can we meet next week" is about the demo, not the buying timeline
    if not forward and not phrase.lower().startswith(_URGENT_PREFIX):
        return None  # "our Q3 was rough" is history, not a plan
    return phrase


NEED_RE = re.compile(
    r"\b(?:we need(?: to)?|we'?re looking (?:for|to)|we are looking (?:for|to)|i'?m looking (?:for|to)|looking for"
    r"|our (?:biggest |main |real )?(?:problem|challenge|issue|pain(?: point)?|bottleneck) is|(?:we'?re|we are|i'?m) struggling (?:with|to)"
    r"|we struggle (?:with|to)|we want to|we'?d like to|the goal is to|(?:we'?re|we are) trying to)\s+([^.?!;]{3,120})",
    re.I,
)
KEEP_RE = re.compile(r"\bwe keep (missing|losing|dropping) ([^.?!;]{3,60})", re.I)
NEED_EXCLUDE_RE = re.compile(
    r"^(?:a |the |to |an )?(?:demo|meeting|call|walkthrough|book|schedule|talk|speak|know|see|hear|understand|compare|go live|launch"
    r"|roll ?out|decide|buy|purchase|price|pricing|cost|human|person)\b",
    re.I,
)
_CLAUSE_SPLIT_RE = re.compile(r"\s[—–-]\s|,\s*(?:and|but|so)\s|\s(?:and|but)\s(?:our|we|i|my)\b", re.I)


def extract_pain_points(text: str) -> List[str]:
    pains: List[str] = []
    for m in NEED_RE.finditer(text):
        phrase = _CLAUSE_SPLIT_RE.split(m.group(1))[0].strip(" ,")
        if len(phrase) >= 3 and not NEED_EXCLUDE_RE.search(phrase):
            pains.append(phrase[:90])
    for m in KEEP_RE.finditer(text):
        pains.append(f"{m.group(1)} {_CLAUSE_SPLIT_RE.split(m.group(2))[0].strip(' ,')}"[:90])
    return pains[:3]


# ---------------------------------------------------------------- competitors & objections

_COMPETITORS = [
    ("OpenAI Realtime", re.compile(r"\bopenai\b|\brealtime api\b|\bgpt-?4o\b", re.I)),
    ("Twilio", re.compile(r"\btwilio\b", re.I)),
    ("Vapi", re.compile(r"\bvapi\b", re.I)),
    ("Bland", re.compile(r"\bbland(?: ai)?\b", re.I)),
    ("Retell", re.compile(r"\bretell\b", re.I)),
    ("ElevenLabs", re.compile(r"\beleven ?labs\b", re.I)),
    ("Synthflow", re.compile(r"\bsynthflow\b", re.I)),
]
WHY_YOU_RE = re.compile(r"\bwhy (?:should|would) (?:we|i) (?:choose|pick|go with|use|switch to|pay) (?:you|lively)\b", re.I)

OBJECTION_RES = {
    "pricing": re.compile(
        r"\b(?:too (?:expensive|pricey|costly|much)|expensive|pricey|overpriced|costly|can'?t afford|cannot afford"
        r"|(?:out of|over|beyond|above) (?:our|my) budget|cheaper|discount|lower (?:the )?price|budget (?:is )?(?:tight|limited|small)"
        r"|no budget|(?:price|cost) is (?:high|steep|a lot)|steep|pay (?:you )?more)\b",
        re.I,
    ),
    "latency": re.compile(r"\b(?:latency|laggy|lag|delays?|too slow|slow to respond|awkward pauses|barge[- ]?in|talk over)\b", re.I),
    "trust": re.compile(
        r"\b(?:(?:don'?t|do not|can'?t|cannot) trust|trust (?:ai|it|a bot|this|robots?)|hallucinat\w*|make (?:things|stuff) up|made[- ]up"
        r"|wrong answers?|says? the wrong|how (?:do|would|can) (?:i|we) know|accura(?:te|cy)|reliab(?:le|ility)|what if it (?:says|gets|makes)"
        r"|sounds? robotic|customers? (?:won'?t|will not|don'?t|do not) (?:like|want|trust)|skeptical|sceptical|burned before"
        r"|another (?:ai )?chatbot|just a bot)\b",
        re.I,
    ),
    "security": re.compile(
        r"\b(?:privacy|private data|(?:my|our|customer|patient) data|data (?:security|protection|retention|residency)|secure|security"
        r"|gdpr|hipaa|soc ?2|compliance|compliant|encrypt\w*|data leak\w*)\b",
        re.I,
    ),
    "product": re.compile(
        r"\b(?:too (?:complex|complicated)|complicated|hard to (?:set up|use|integrate|implement|learn)|difficult to (?:set up|use|integrate|implement|learn)"
        r"|(?:does(?:n'?t| not)|can'?t|cannot|won'?t|will not) (?:integrate|support|handle|work with)|not sure (?:it|this|you) can"
        r"|missing (?:a |the )?features?|features? (?:is |are )?missing|lacks? (?:a |the )?features?|migrat\w+|switching costs?"
        r"|learning curve|(?:long|lengthy) (?:setup|onboarding))\b",
        re.I,
    ),
}


def extract_competitor(lower: str) -> Optional[str]:
    for name, pattern in _COMPETITORS:
        if pattern.search(lower):
            return name
    return None


# ---------------------------------------------------------------- intent signals

HUMAN_RE = re.compile(
    r"\b(?:(?:talk|speak|chat) (?:to|with) (?:a |an |your |the |some )?(?:human|real person|person|someone|somebody|manager|supervisor"
    r"|sales ?(?:rep|person)|account executive|representative|rep|people|team member|live agent)"
    r"|(?:human|live) (?:agent|rep|representative|person|being)|real (?:person|human)|transfer me|connect me (?:to|with)"
    r"|escalate (?:this|me)|get (?:me )?(?:a |your )?(?:manager|supervisor|human))\b",
    re.I,
)
_NEGATION_BEFORE_RE = re.compile(r"\b(?:no need|don'?t need|do not need|don'?t want|do not want|not)\b[^.?!]{0,25}$", re.I)
LEGAL_RE = re.compile(
    r"\b(?:msa|master (?:services? )?agreement|custom (?:contract|terms|pricing agreement)|contract terms|legal (?:team|review|terms|department)"
    r"|redlines?|dpa|data processing agreement|procurement|security (?:questionnaire|review)|baa|business associate agreement"
    r"|sla (?:negotiation|terms|credits)|indemnif\w+|liability (?:cap|clause))\b",
    re.I,
)
FRUSTRATION_RE = re.compile(
    r"\b(?:frustrat\w*|annoy\w*|useless|waste of (?:my |our )?time|ridiculous|not helping|this is (?:bad|terrible|pointless)"
    r"|talked to (?:three|3|two|2|several|multiple|so many) (?:people|reps|agents)|explain(?:ing)? (?:everything |this |it )?again"
    r"|repeat(?:ing)? myself|going in circles)\b",
    re.I,
)
POSITIVE_RE = re.compile(r"\b(?:great|awesome|perfect|love (?:it|that)|excellent|impressive|sounds (?:good|great)|that helps|nice)\b", re.I)
ACCEPT_RE = re.compile(
    r"\b(?:that makes sense|makes sense|fair enough|that'?s fair|that helps|good to know|got it|understood|i see|that works"
    r"|sounds (?:good|fair|reasonable|great)|okay|ok|alright|perfect|cool|great)\b",
    re.I,
)
PRICE_QUESTION_RE = re.compile(r"\b(?:price|pricing|cost|how much|plans?|tiers?)\b", re.I)

# Scheduling
CAPABILITY_QUERY_RE = re.compile(
    r"\b(?:show|give|hear|see|try|test|do)\s+(?:me\s+)?(?:a\s+)?(?:quick\s+|live\s+)?(?:demo|demonstration)\b"
    r"|\b(?:demo\s+of|demo\s+your|voice\s+demo|product\s+demo)\b"
    r"|\b(?:can|could)\s+you\s+(?:demo|demonstrate)\b",
    re.I,
)
CURRENT_CALL_RE = re.compile(
    r"\b(?:on|during|end|start|about|for|finish)\s+(?:this|the|our)\s+call\b"
    r"|\b(?:call\s+latency|call\s+quality|phone\s+call|voice\s+call|this\s+call)\b"
    r"|\bcan\s+you\s+hear\s+me\b"
    r"|\bhow\s+does\s+this\s+call\s+work\b",
    re.I,
)
GREETING_RE = re.compile(r"^\s*(?:hello|hi|hey|good\s+(?:morning|afternoon|evening)|howdy|greetings)[\s!.,?]*$", re.I)
_MEETING_NOUN = r"(?:demo|walkthrough|meeting|appointment|session|time\s*slot|call\s+with\s+(?:a|the|your)?\s*architect)"
EXPLICIT_SCHEDULE_RE = re.compile(
    rf"\b(?:schedule|book|reserve|set\s*up|arrange|lock\s*in|organize)\s+(?:a\s+|the\s+|our\s+|an\s+)?(?:[\w-]+\s+){{0,3}}?{_MEETING_NOUN}\b"
    r"|\b(?:book|schedule|reserve)\s+(?:some\s+)?(?:time|a\s+slot|a\s+call)\b"
    r"|\b(?:send|email)\s+(?:me\s+)?(?:the\s+|a\s+)?(?:calendar\s*invite|calendar\s*link|meeting\s*link|invite)\b"
    r"|\b(?:want|like)\s+to\s+(?:schedule|book|reserve|set\s*up|see)\s+(?:a\s+|an\s+)?(?:[\w-]+\s+){0,2}?(?:demo|meeting|walkthrough|call)\b"
    r"|\bcan\s+we\s+(?:schedule|book|reserve|set\s*up)\s+(?:a\s+|an\s+)?(?:[\w-]+\s+){0,3}?(?:demo|meeting|walkthrough|call)\b",
    re.I,
)
RESCHEDULE_RE = re.compile(
    r"\b(?:reschedule|change\s+(?:the\s+)?time|different\s+time|move\s+(?:the\s+|it\s+|our\s+)?(?:demo|meeting|walkthrough|call|to)"
    r"|push\s+it\s+to|make\s+it|change\s+it\s+to|switch\s+(?:it\s+)?to|can\s+we\s+do\s+(?:another|a\s+different))\b",
    re.I,
)
CANCEL_RE = re.compile(r"\bcancel\b", re.I)
DONT_CANCEL_RE = re.compile(r"\b(?:don'?t|do not|no need to)\s+cancel\b", re.I)
DECLINE_VERB_RE = re.compile(
    r"\b(?:don'?t|do not|no need to|not ready to|not going to|won'?t|will not|wouldn'?t|would not|never)\s+(?:(?:want|need|like|plan) to\s+)?"
    r"(?:book|schedule|set\s*up|arrange|lock\s*(?:it\s*)?in|reserve)\b",
    re.I,
)
DECLINE_NOUN_RE = re.compile(r"\bnot (?:interested in|ready for) (?:a |the |any )?(?:demo|meeting|call|walkthrough)\b|\bno (?:demo|meeting)s?\b", re.I)
DECLINE_TIMING_RE = re.compile(r"\b(?:hold off|maybe later|not (?:right )?now|not yet|not today|some other time)\b", re.I)
MEETING_WORD_RE = re.compile(r"\b(?:demo|meeting|call|walkthrough|appointment|slot|book|booking|schedule|invite)\b", re.I)
BUYER_AGREED_RE = re.compile(
    r"\b(?:that\s+works|works\s+for\s+me|sounds\s+good|lock\s+it\s+in|let'?s\s+do\s+(?:that|it|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"|\d+\s*(?:am|pm)\s+works|perfect\s+let'?s\s+do\s+it|yes\s+let'?s\s+do\s+that|yes\s+please\s+book|book\s+it|go\s+ahead)\b",
    re.I,
)
SLOT_CHOICE_RE = re.compile(r"\b(?:the\s+)?(first|1st|second|2nd|third|3rd|last)\s+(?:one|option|slot|time)\b|\bthe\s+(first|second|third|last)\b", re.I)
_ORDINALS = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2, "last": -1}


SLOT_NOUN_RE = re.compile(r"\b(?:demo|walkthrough|meeting|appointment|slot|call|session)\b", re.I)


def _rule_demo_request(lower: str) -> Optional[str]:
    if CANCEL_RE.search(lower) and not DONT_CANCEL_RE.search(lower) and MEETING_WORD_RE.search(lower + " demo"):
        return "cancel"
    if DECLINE_VERB_RE.search(lower) or DECLINE_NOUN_RE.search(lower) or (DECLINE_TIMING_RE.search(lower) and MEETING_WORD_RE.search(lower)):
        return "decline"
    if CAPABILITY_QUERY_RE.search(lower) or CURRENT_CALL_RE.search(lower) or GREETING_RE.search(lower):
        return None
    if RESCHEDULE_RE.search(lower):
        return "reschedule"
    if EXPLICIT_SCHEDULE_RE.search(lower):
        return "request"
    if extract_day(lower) and extract_time(lower) and SLOT_NOUN_RE.search(lower):
        return "request"
    return None


# ---------------------------------------------------------------- day / time / duration

_WEEKDAY = r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
_MONTH_ABBR = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
DAY_RE = re.compile(
    rf"\b((?:next|this|coming)\s+{_WEEKDAY}|{_WEEKDAY}(?:\s*,?\s*{_MONTH_ABBR}\s+\d{{1,2}}(?:st|nd|rd|th)?)?|day after tomorrow|tomorrow|today)\b",
    re.I,
)
MONTH_DAY_RE = re.compile(rf"\b({_MONTH_ABBR}\s+\d{{1,2}}(?:st|nd|rd|th)?)\b", re.I)
_HOUR_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
_HOUR_TOKEN = r"(?:1[0-2]|0?[1-9]|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
DIGIT_TIME_RE = re.compile(r"\b((?:1[0-2]|0?[1-9])(?::[0-5]\d)?)\s*(am|pm|a\.m\.|p\.m\.)(?![a-z])", re.I)
WORD_TIME_RE = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*(am|pm|a\.m\.|p\.m\.)(?![a-z])", re.I)
AT_TIME_RE = re.compile(rf"\b(?:at|around)\s+({_HOUR_TOKEN})(?!\s*(?:mins|minutes|min|hour|hours|users|seats|reps|percent|k|thousand))\b", re.I)
PART_OF_DAY_RE = re.compile(rf"\b({_HOUR_TOKEN})\s+(?:in the\s+)?(morning|afternoon|evening)\b", re.I)
OCLOCK_RE = re.compile(rf"\b({_HOUR_TOKEN})\s*o'?clock\b", re.I)
DURATION_RE = re.compile(
    r"\b(\d+)\s*-?\s*(mins?|minutes?|hours?|hrs?)\b|\bhalf(?:\s+an)?\s+hour\b|\b(ten|fifteen|thirty|forty-five|sixty)[- ]min(?:ute)?s?\b",
    re.I,
)
_WORD_MINUTES = {"ten": 10, "fifteen": 15, "thirty": 30, "forty-five": 45, "sixty": 60}


def extract_day(lower: str) -> Optional[str]:
    m = DAY_RE.search(lower) or MONTH_DAY_RE.search(lower)
    return m.group(1).strip().title() if m else None


def _hour(token: str) -> int:
    token = token.lower()
    return _HOUR_WORDS[token] if token in _HOUR_WORDS else int(token)


def extract_time(lower: str) -> Optional[str]:
    m = DIGIT_TIME_RE.search(lower)
    if m:
        hour, _, minute = m.group(1).partition(":")
        return f"{int(hour)}:{minute or '00'} {'PM' if m.group(2).lower().startswith('p') else 'AM'}"
    m = WORD_TIME_RE.search(lower)
    if m:
        return f"{_hour(m.group(1))}:00 {'PM' if m.group(2).lower().startswith('p') else 'AM'}"
    m = AT_TIME_RE.search(lower)
    if m:
        hour = _hour(m.group(1))
        period = "PM" if hour in (1, 2, 3, 4, 5, 6, 7) or re.search(r"\b(?:afternoon|evening|tonight)\b", lower) else "AM"
        return f"{hour}:00 {period}"
    m = PART_OF_DAY_RE.search(lower)
    if m:
        return f"{_hour(m.group(1))}:00 {'AM' if m.group(2).lower() == 'morning' else 'PM'}"
    m = OCLOCK_RE.search(lower)
    if m:
        hour = _hour(m.group(1))
        return f"{hour}:00 {'PM' if hour in (1, 2, 3, 4, 5, 6, 7) or 'afternoon' in lower or 'evening' in lower else 'AM'}"
    # Never bare "morning"/"afternoon", which would catch "Good morning"
    if re.search(r"\b(?:in\s+the|tomorrow|this)\s+morning\b", lower):
        return "10:00 AM"
    if re.search(r"\b(?:in\s+the|tomorrow|this)\s+afternoon\b", lower):
        return "2:00 PM"
    if re.search(r"\b(?:in\s+the|tomorrow|this)\s+evening\b", lower):
        return "5:00 PM"
    return None


def extract_duration(lower: str) -> str:
    minutes = 30
    m = DURATION_RE.search(lower)
    if m:
        if m.group(1):
            value = int(m.group(1))
            minutes = value * 60 if m.group(2).lower().startswith(("hour", "hr")) else value
        elif m.group(3):
            minutes = _WORD_MINUTES[m.group(3).lower()]
    return f"{min(max(minutes, 10), 120)} mins"


def duration_minutes(label: str) -> int:
    m = re.search(r"(\d+)\s*mins", label)
    return int(m.group(1)) if m else 30


def _unnegated(pattern: re.Pattern, lower: str) -> bool:
    for m in pattern.finditer(lower):
        if not _NEGATION_BEFORE_RE.search(lower[: m.start()]):
            return True
    return False


def rule_based_understanding(text: str) -> Dict[str, Any]:
    u = empty_understanding("rules")
    lower = text.lower()
    u["email"] = extract_email(text)
    u["user_count"] = extract_user_count(lower)
    u["budget"] = extract_budget(lower)
    u["role"], u["is_decision_maker"] = extract_authority(lower)
    u["timeline"] = extract_timeline(text)
    u["pain_points"] = extract_pain_points(text)
    u["competitor"] = extract_competitor(lower)

    types = [t for t, pattern in OBJECTION_RES.items() if pattern.search(lower)]
    if u["competitor"] or WHY_YOU_RE.search(lower):
        types.append("competitor")
    u["objections"] = [{"type": t, "summary": text.strip()[:160]} for t in dict.fromkeys(types)]

    u["wants_human"] = _unnegated(HUMAN_RE, lower)
    u["legal_or_contract"] = bool(LEGAL_RE.search(lower))
    u["demo_request"] = _rule_demo_request(lower)
    u["agrees_to_proposal"] = bool(BUYER_AGREED_RE.search(lower))
    choice = SLOT_CHOICE_RE.search(lower)
    if choice:
        u["slot_choice"] = _ORDINALS[(choice.group(1) or choice.group(2)).lower()]
    u["accepts_previous_answer"] = bool(ACCEPT_RE.search(lower)) and not u["objections"]

    if FRUSTRATION_RE.search(lower):
        u["sentiment"] = "Frustrated"
    elif "trust" in types:
        u["sentiment"] = "Skeptical"
    elif types:
        u["sentiment"] = "Hesitant"
    elif POSITIVE_RE.search(lower):
        u["sentiment"] = "Positive"

    if u["wants_human"]:
        u["intent"] = "request_human"
    elif u["demo_request"]:
        u["intent"] = f"{u['demo_request']}_demo"
    elif u["objections"]:
        u["intent"] = "raise_objection"
    elif PRICE_QUESTION_RE.search(lower):
        u["intent"] = "ask_pricing"
    elif "?" in text:
        u["intent"] = "ask_product"
    elif any(u[k] for k in ("user_count", "budget", "role", "timeline", "pain_points", "email")):
        u["intent"] = "provide_info"
    return u


# ---------------------------------------------------------------- LLM path

def _clean_str(value: Any, max_len: int = 120) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or value.lower() in ("null", "none", "unknown", "n/a", "na"):
        return None
    return value[:max_len]


def normalize_llm_understanding(raw: Dict[str, Any], text: str) -> Dict[str, Any]:
    u = empty_understanding("llm")
    u["intent"] = _clean_str(raw.get("intent"), 40) or "other"
    demo_request = _clean_str(raw.get("demo_request"), 20)
    u["demo_request"] = demo_request if demo_request in DEMO_REQUESTS else None
    u["requested_time_text"] = _clean_str(raw.get("requested_time"), 80)
    choice = raw.get("slot_choice")
    if isinstance(choice, int) and 1 <= choice <= 3:
        u["slot_choice"] = choice - 1
    for key in ("agrees_to_proposal", "accepts_previous_answer", "wants_human", "legal_or_contract"):
        u[key] = raw.get(key) is True
    u["user_count"] = parse_count(raw.get("user_count"))
    u["budget"] = _clean_str(raw.get("budget"), 60)
    u["timeline"] = _clean_str(raw.get("timeline"), 60)
    role = _clean_str(raw.get("role"), 60)
    u["role"] = format_role(role) if role and not role.lower().startswith("reports to") else role
    dm = raw.get("is_decision_maker")
    u["is_decision_maker"] = dm if isinstance(dm, bool) else None
    u["company"] = _clean_str(raw.get("company"), 80)
    u["competitor"] = _clean_str(raw.get("competitor"), 40)
    pains = raw.get("pain_points") if isinstance(raw.get("pain_points"), list) else []
    u["pain_points"] = [p for p in (_clean_str(x, 90) for x in pains) if p][:3]
    objections = []
    for item in raw.get("objections") or []:
        obj_type = item.get("type") if isinstance(item, dict) else item
        if isinstance(obj_type, str) and obj_type.lower() in OBJECTION_TYPES and obj_type.lower() not in [o["type"] for o in objections]:
            summary = _clean_str(item.get("summary"), 160) if isinstance(item, dict) else None
            objections.append({"type": obj_type.lower(), "summary": summary or text.strip()[:160]})
    u["objections"] = objections
    sentiment = _clean_str(raw.get("sentiment"), 20)
    u["sentiment"] = sentiment.capitalize() if sentiment and sentiment.capitalize() in SENTIMENTS else None
    # Addresses come from the transcript itself, with LLM structured fallback if present
    extracted = extract_email(text)
    if not extracted and raw.get("email"):
        extracted = extract_email(str(raw.get("email")))
    u["email"] = extracted
    return u


class LLMUnderstanding:
    def __init__(self):
        self.client = None
        self.stats = {"llm": 0, "timeout": 0, "error": 0}
        if settings.GROQ_API_KEY:
            try:
                from groq import AsyncGroq
                self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            except Exception as e:
                logger.warning(f"LLM understanding disabled: {e}")

    async def extract(self, text: str, state: Any) -> Optional[Dict[str, Any]]:
        """Structured understanding of one buyer turn, or None (caller falls back to rules)."""
        if not self.client or not text.strip():
            return None
        payload = {
            "last_agent_turn": next((t.content for t in reversed(state.transcript) if t.role == "agent"), None),
            "recent_buyer_turns": [t.content for t in state.transcript if t.role == "buyer"][-3:],
            "known": {
                "users": state.users,
                "budget": state.budget,
                "timeline": state.timeline,
                "role": state.bant.authority.get("role"),
                "confirmed_demo": (state.scheduled_demo or {}).get("time"),
                "offered_slots": (state.slot_conflict or {}).get("alternatives") or state.available_slots,
                "open_objections": [o.type for o in state.active_objections],
            },
            "new_buyer_turn": text,
        }
        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=settings.EXTRACTION_MODEL,
                    messages=[
                        {"role": "system", "content": UNDERSTANDING_EXTRACTION_PROMPT},
                        {"role": "user", "content": json.dumps(payload)},
                    ],
                    temperature=0,
                    max_tokens=350,
                    response_format={"type": "json_object"},
                ),
                timeout=settings.EXTRACTION_TIMEOUT_SECONDS,
            )
            raw = json.loads(response.choices[0].message.content or "{}")
            self.stats["llm"] += 1
            return normalize_llm_understanding(raw if isinstance(raw, dict) else {}, text)
        except asyncio.TimeoutError:
            self.stats["timeout"] += 1
            logger.info(f"LLM understanding exceeded {settings.EXTRACTION_TIMEOUT_SECONDS}s; using rules for this turn.")
        except Exception as e:
            self.stats["error"] += 1
            logger.warning(f"LLM understanding failed ({e}); using rules for this turn.")
        return None


llm_understanding = LLMUnderstanding()
