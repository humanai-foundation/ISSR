crisis_lexicon = {
    "mental_health": {
        "explicit": [
            "depression", "anxiety", "hopeless", "overwhelmed", "panic attack", "social anxiety", "PTSD",
            "flashbacks", "nightmares", "dissociation", "intrusive thoughts", "trauma", "worthless", "numb",
            "empty", "self-hate", "isolated", "exhausted", "insomnia", "brain fog", "mood swings", "crying",
            "irritable", "emotional pain", "stress", "burnout", "mental breakdown", "disconnected", "lonely",
            "fear", "can’t breathe", "racing thoughts", "uncontrollable thoughts", "guilt", "shame",
            "unmotivated", "feeling lost", "no energy", "feeling stuck", "lack of focus", "can’t function",
            "losing interest", "fatigue", "restless", "self-doubt", "low self-esteem", "can’t concentrate",
            "overthinking", "avoiding people", "heart racing", "bipolar disorder", "manic episode", "depressive episode",
            "psychosis", "schizophrenia", "dissociative identity disorder", "borderline personality disorder", "OCD",
            "eating disorder", "self-harm", "cutting", "burning", "scratching", "hair pulling", "skin picking"
        ],
        "coded": [
            "low spoons", "heavy chest", "stuck in my head", "faking smiles", "pretending to be okay",
            "can’t mask anymore", "floating away", "trapped in my mind", "checked out", "shutting down",
            "mind is dark", "crawling skin", "no escape", "lost in a loop", "echo chamber", "NPC",
            "ghost mode", "just background noise", "permanent headache", "seeing static", "grey days",
            "can’t wake up", "everything is too much", "drowning in thoughts", "the void", "static noise in my head",
            "too tired to exist", "mind racing nonstop", "watching from the outside", "just surviving",
            "in my bubble", "white noise brain", "time slipping away", "everything feels fake", "no feeling left",
            "pretending to care", "nobody notices", "losing myself", "shadow of myself"
        ]
    },
    "suicide": {
        "explicit": [
            "suicide", "end my life", "kill myself", "no reason to live", "want to die", "take my life",
            "self-harm", "overdose", "jump off", "hang myself", "poison myself", "gun to my head",
            "rope", "final decision", "permanent solution", "giving up", "goodbye message", "can’t keep going",
            "done fighting", "no more pain", "too much to handle", "empty inside", "tired of everything",
            "can’t escape", "no future", "last chance", "no point anymore", "nobody would care", "the pain won",
            "losing control", "final thoughts", "goodbye world", "writing a note", "checking out",
            "sleep forever", "want to disappear", "can’t go on", "ready to leave", "the end is near",
            "don’t wake up", "fading away", "unbearable pain", "crushed inside", "nothing left to give",
            "nothing left to lose", "life is pointless", "done with everything", "no second chances",
            "only one way out"
        ],
        "coded": [
            "KMS", "unalive", "permanent nap", "going to sleep forever", "catching the bus", "rope game",
            "taking the exit", "no respawn", "checking out early", "logging off for good", "closing my book",
            "gone fishing", "see you on the other side", "one way trip", "empty chair soon", "no more reruns",
            "lights out", "fading signal", "CTRL + ALT + DELETE", "end scene", "GG", "long ride", "no tomorrow",
            "last sunrise", "countdown started", "signing off", "done pretending", "no more next time",
            "too tired to restart", "can’t respawn this time", "silent mode forever", "taking my final bow",
            "no more chapters left", "final logout", "going ghost", "shutting down for good",
            "see you in another life", "just a memory soon", "yeet", "CTB", "SH", "final yeet", "taking the L",
            "logging off", "permanent sleep", "no respawn", "final exit", "see you on the other side", "one way trip",
            "lights out", "fading signal", "CTRL + ALT + DELETE", "end scene", "GG", "long ride", "no tomorrow",
            "last sunrise", "countdown started", "signing off", "done pretending", "no more next time",
            "too tired to restart", "can’t respawn this time", "silent mode forever", "taking my final bow",
            "no more chapters left", "final logout", "going ghost", "shutting down for good",
            "see you in another life", "just a memory soon"
        ]
    },
    "substance_use": {
        "explicit": [
            "alcoholic", "drunk", "high", "cocaine", "heroin", "meth", "pills", "painkillers", "Xanax",
            "fentanyl", "addiction", "rehab", "withdrawal", "overdose", "OD", "drugged out", "binge drinking",
            "blackout", "opiates", "stimulants", "narcotics", "prescription abuse", "substance abuse",
            "dealer", "relapse", "detox", "cold turkey", "mixing drugs", "taking too much", "need another hit",
            "pushing limits", "can’t quit", "always craving", "hooked", "strung out", "need a fix",
            "chasing the high", "spiraling", "downward spiral", "numb the pain", "out of control",
            "can’t stop", "slurring speech", "losing grip", "body shutting down", "no more control",
            "shaky hands", "nightly drinking", "losing memory", "fentanyl", "methamphetamine", "crack cocaine",
            "LSD", "ecstasy", "ketamine", "mushrooms", "spice", "synthetic opioids", "bath salts", "GHB",
            "roofies", "date rape drugs", "inhalants", "nitrous oxide"
        ],
        "coded": [
            "snow", "smack", "molly", "lean", "benzos", "bars", "percs", "dope", "zaza", "nod", "candy flipping",
            "skittles", "chasing dragons", "plug", "gassed", "geeked", "wired", "faded", "blow", "black tar",
            "speedball", "cloud 9", "laced", "ripped", "popped a bean", "shot up", "420", "bump",
            "plug hit me up", "one more round", "sippin’", "cooking up", "jib", "Xannies", "tweak",
            "on a bender", "too deep", "red eyes"
        ]
    }
}

keywords = (
    crisis_lexicon['mental_health']['explicit'] + 
    crisis_lexicon['mental_health']['coded'] + 
    crisis_lexicon['substance_use']['explicit'] + 
    crisis_lexicon['substance_use']['coded'] +
    crisis_lexicon['suicide']['explicit'] + 
    crisis_lexicon['suicide']['coded']
)
