"""Starter rhythm library: ORIGINAL pattern definitions only (no recordings or melodies).

Beat units are the pulse that ``bpm`` counts (a quarter note in 4/4; a dotted quarter in 12/8).
No two events share a beat: Phase 1 scoring is voice-agnostic, so simultaneous strikes would be
heard as one. Cultural notes MUST be reviewed by a knowledgeable musician before launch.
"""

T = 1 / 3  # triplet third of a beat
LICENSE = "Original pattern definition by Eye Forge Studios for Qi Rhythm."


def ev(*items):
    out = []
    for it in items:
        beat, voice = it[0], it[1]
        e = {"beat": round(beat, 4), "voice": voice}
        if len(it) > 2 and it[2]:
            e["accent"] = True
        out.append(e)
    return out


def twice(bar, length=4):
    """Repeat a one-bar list of (beat, voice[, accent]) tuples over two bars."""
    return list(bar) + [(b + length, *rest) for b, *rest in bar]


def rhythm(slug, title, difficulty, bpm, events, length=8, ts="4/4", subdivision=4, count_in=4):
    return {
        "slug": slug,
        "title": title,
        "difficulty": difficulty,
        "bpm": bpm,
        "time_signature": ts,
        "length_beats": length,
        "pattern": {
            "subdivision": subdivision,
            "count_in_beats": count_in,
            "length_beats": length,
            "events": ev(*events),
        },
        "source": "original",
        "license_notes": LICENSE,
    }


GENRES = [
    {
        "slug": "jazz-swing",
        "name": "Jazz & Swing",
        "description": "Bouncy, lilting rhythms where the off-beats lean a little late.",
        "cultural_notes": (
            "Jazz grew from African American communities in New Orleans in the early 1900s, "
            "blending blues, ragtime, brass-band, and church music traditions. Swing became the "
            "popular dance music of the 1930s and 40s, and its relaxed 'long-short' feel is still "
            "at the heart of jazz today."
        ),
        "rhythms": [
            rhythm(
                "jazz-claps-two-four",
                "Claps on Two and Four",
                "beginner",
                92,
                twice([(1, "clap", True), (3, "clap", True)]),
            ),
            rhythm(
                "jazz-walking-pulse",
                "Walking Pulse",
                "beginner",
                96,
                twice([(0, "low"), (1, "high", True), (2, "low"), (3, "high", True)]),
            ),
            rhythm(
                "jazz-swing-ride",
                "Swing Ride Feel",
                "beginner",
                88,
                twice(
                    [
                        (0, "high"),
                        (1, "high", True),
                        (1 + 2 * T, "high"),
                        (2, "high"),
                        (3, "high", True),
                        (3 + 2 * T, "high"),
                    ]
                ),
                subdivision=3,
            ),
            rhythm(
                "jazz-shuffle",
                "Easy Shuffle",
                "intermediate",
                92,
                twice(
                    [
                        (b + o, "low" if o == 0 else "high", o == 0 and b % 2 == 1)
                        for b in range(4)
                        for o in (0, 2 * T)
                    ]
                ),
                subdivision=3,
            ),
            rhythm(
                "jazz-simple-syncopation",
                "Simple Syncopation",
                "intermediate",
                100,
                [
                    (0, "low", True),
                    (1 + 2 * T, "high"),
                    (3, "low"),
                    (4, "low", True),
                    (5 + 2 * T, "high"),
                    (6 + 2 * T, "high"),
                    (7, "clap"),
                ],
                subdivision=3,
            ),
            rhythm(
                "jazz-charleston",
                "Charleston Bounce",
                "advanced",
                112,
                [
                    (0, "low", True),
                    (1.5, "high"),
                    (3 + 2 * T, "clap"),
                    (4, "low", True),
                    (5.5, "high"),
                    (6 + 2 * T, "high"),
                    (7 + 2 * T, "clap"),
                ],
                subdivision=6,
            ),
        ],
    },
    {
        "slug": "funk-soul",
        "name": "Funk & Soul",
        "description": "Strong backbeats and tight, danceable grooves.",
        "cultural_notes": (
            "Soul music came out of African American gospel and rhythm and blues in the 1950s and "
            "60s, with record labels in cities like Detroit and Memphis shaping its sound. Funk "
            "followed in the late 1960s, putting the groove first with emphasis on the first beat "
            "and interlocking parts."
        ),
        "rhythms": [
            rhythm(
                "funk-basic-backbeat",
                "Basic Backbeat",
                "beginner",
                92,
                twice([(0, "low"), (1, "clap", True), (2, "low"), (3, "clap", True)]),
            ),
            rhythm(
                "soul-tambourine",
                "Tambourine Two and Four",
                "beginner",
                100,
                twice([(0, "shaker"), (1, "shaker", True), (2, "shaker"), (3, "shaker", True)]),
            ),
            rhythm(
                "soul-stomp",
                "Soul Stomp",
                "beginner",
                88,
                twice([(0, "low", True), (1, "clap"), (2, "low"), (2.5, "low"), (3, "clap")]),
            ),
            rhythm(
                "funk-simple-groove",
                "Simple Funk Groove",
                "intermediate",
                94,
                [
                    (0, "low", True),
                    (1, "clap"),
                    (1.75, "low"),
                    (2.5, "low"),
                    (3, "clap"),
                    (4, "low", True),
                    (5, "clap"),
                    (6.5, "low"),
                    (7, "clap"),
                    (7.5, "high"),
                ],
            ),
            rhythm(
                "soul-pickup-groove",
                "Soul Pickup Groove",
                "intermediate",
                98,
                twice(
                    [
                        (0, "low", True),
                        (1, "clap"),
                        (1.5, "high"),
                        (2.5, "low"),
                        (3, "clap"),
                        (3.5, "high"),
                    ]
                ),
            ),
            rhythm(
                "funk-sixteenths",
                "Funk Sixteenths",
                "advanced",
                96,
                [
                    (0, "low", True),
                    (0.75, "high"),
                    (1, "clap"),
                    (1.75, "low"),
                    (2.5, "low"),
                    (3, "clap"),
                    (3.75, "high"),
                    (4, "low", True),
                    (4.75, "low"),
                    (5, "clap"),
                    (6.25, "high"),
                    (6.5, "low"),
                    (7, "clap"),
                ],
            ),
        ],
    },
    {
        "slug": "hip-hop",
        "name": "Hip-Hop",
        "description": "Head-nodding beats built from a deep 'boom' and a sharp 'bap'.",
        "cultural_notes": (
            "Hip-hop began in the Bronx, New York, in the 1970s at block parties where DJs looped "
            "the drum breaks of funk and soul records. Young African American, Puerto Rican, and "
            "Caribbean-American artists built a culture of rhyme, dance, and art around these beats."
        ),
        "rhythms": [
            rhythm(
                "hiphop-boom-bap",
                "Boom-Bap Basic",
                "beginner",
                86,
                twice([(0, "low", True), (1, "clap"), (2.5, "low"), (3, "clap")]),
            ),
            rhythm(
                "hiphop-head-nod",
                "Head Nod",
                "beginner",
                84,
                twice([(0, "low", True), (0.5, "low"), (1, "clap"), (3, "clap")]),
            ),
            rhythm(
                "hiphop-old-school",
                "Old-School Groove",
                "intermediate",
                92,
                [
                    (0, "low", True),
                    (1, "clap"),
                    (1.75, "low"),
                    (2.5, "low"),
                    (3, "clap"),
                    (4, "low", True),
                    (4.5, "low"),
                    (5, "clap"),
                    (6.5, "low"),
                    (7, "clap"),
                ],
            ),
            rhythm(
                "hiphop-swing-bap",
                "Swung Boom-Bap",
                "advanced",
                90,
                [
                    (0, "low", True),
                    (2 * T, "high"),
                    (1, "clap"),
                    (1 + 2 * T, "high"),
                    (2.5, "low"),
                    (3, "clap"),
                    (3 + 2 * T, "low"),
                    (4, "low", True),
                    (5, "clap"),
                    (6.5, "low"),
                    (7, "clap"),
                    (7 + 2 * T, "high"),
                ],
                subdivision=6,
            ),
        ],
    },
    {
        "slug": "latin",
        "name": "Latin",
        "description": "Rhythms from Cuba and the Spanish-speaking Caribbean, built on the clave.",
        "cultural_notes": (
            "The clave is a two-bar rhythmic key at the heart of Afro-Cuban music, carrying West "
            "African rhythmic ideas brought to Cuba by enslaved people. Son clave guides son, "
            "salsa, and mambo, while rumba clave comes from the Afro-Cuban rumba tradition. "
            "Merengue is the national dance music of the Dominican Republic."
        ),
        "rhythms": [
            rhythm(
                "latin-son-clave-32",
                "Son Clave 3-2",
                "beginner",
                90,
                [(0, "high", True), (1.5, "high"), (3, "high"), (5, "high", True), (6, "high")],
            ),
            rhythm(
                "latin-son-clave-23",
                "Son Clave 2-3",
                "beginner",
                90,
                [(1, "high", True), (2, "high"), (4, "high", True), (5.5, "high"), (7, "high")],
            ),
            rhythm(
                "latin-merengue-basic",
                "Basic Merengue",
                "beginner",
                100,
                twice(
                    [
                        (0, "low", True),
                        (1, "low"),
                        (1.5, "high"),
                        (2, "low"),
                        (3, "low"),
                        (3.5, "high"),
                    ]
                ),
            ),
            rhythm(
                "latin-rumba-clave-32",
                "Rumba Clave 3-2",
                "intermediate",
                96,
                [(0, "high", True), (1.5, "high"), (3.5, "high"), (5, "high", True), (6, "high")],
            ),
            rhythm(
                "latin-tumbao-basic",
                "Simple Conga Tumbao",
                "intermediate",
                96,
                twice(
                    [(0, "low"), (1, "high"), (2, "low"), (3, "high", True), (3.5, "high", True)]
                ),
            ),
            rhythm(
                "latin-rumba-clave-23",
                "Rumba Clave 2-3",
                "advanced",
                112,
                [(1, "high", True), (2, "high"), (4, "high", True), (5.5, "high"), (7.5, "high")],
            ),
        ],
    },
    {
        "slug": "caribbean",
        "name": "Caribbean",
        "description": "Laid-back reggae and bright, festive calypso rhythms.",
        "cultural_notes": (
            "Reggae developed in Jamaica in the late 1960s from ska and rocksteady; the 'one drop' "
            "beat leaves the first beat empty and lands the drum on the third. Calypso comes from "
            "Trinidad and Tobago, with roots in West African and French Creole traditions, and is "
            "closely tied to Carnival celebrations."
        ),
        "rhythms": [
            rhythm(
                "caribbean-one-drop",
                "One-Drop Reggae",
                "beginner",
                76,
                twice([(1, "high"), (2, "low", True), (3, "high")]),
            ),
            rhythm(
                "caribbean-calypso-basic",
                "Calypso Basic",
                "beginner",
                100,
                twice(
                    [
                        (0, "low", True),
                        (1, "high"),
                        (1.5, "high"),
                        (2, "low"),
                        (3, "high"),
                        (3.5, "high"),
                    ]
                ),
            ),
            rhythm(
                "caribbean-reggae-upbeats",
                "Reggae Upbeats",
                "intermediate",
                80,
                twice(
                    [(0.5, "shaker"), (1.5, "shaker", True), (2.5, "shaker"), (3.5, "shaker", True)]
                ),
            ),
            rhythm(
                "caribbean-calypso-syncopated",
                "Calypso Bounce",
                "intermediate",
                104,
                twice(
                    [
                        (0, "low", True),
                        (0.75, "high"),
                        (1.5, "high"),
                        (2, "low"),
                        (2.75, "high"),
                        (3.5, "high"),
                    ]
                ),
            ),
        ],
    },
    {
        "slug": "african-diasporic",
        "name": "African & Diasporic",
        "description": "Rolling triple-feel bell patterns and call-and-response phrases.",
        "cultural_notes": (
            "Many West African music traditions, such as those of the Ewe people of Ghana and "
            "Togo, are organized around a repeating bell pattern in a rolling 12/8 feel that "
            "every other part listens to. Call-and-response, where a leader plays or sings and the "
            "group answers, is shared across African and African diasporic music, from work songs "
            "to gospel."
        ),
        "rhythms": [
            rhythm(
                "african-triplet-pulse",
                "Rolling Triplet Pulse",
                "beginner",
                66,
                twice(
                    [
                        (0, "low", True),
                        (2 * T, "high"),
                        (1, "low"),
                        (1 + 2 * T, "high"),
                        (2, "low"),
                        (2 + 2 * T, "high"),
                        (3, "low"),
                        (3 + 2 * T, "high"),
                    ]
                ),
                ts="12/8",
                subdivision=3,
            ),
            rhythm(
                "african-call-response-1",
                "Call and Response: Three and Three",
                "beginner",
                88,
                [
                    (0, "low", True),
                    (1, "low"),
                    (2, "low"),
                    (4, "clap", True),
                    (5, "clap"),
                    (6, "clap"),
                ],
            ),
            rhythm(
                "african-call-response-2",
                "Call and Response: Quick Answer",
                "intermediate",
                92,
                [
                    (0, "low", True),
                    (0.5, "low"),
                    (1, "low"),
                    (2, "high"),
                    (4, "clap", True),
                    (4.5, "clap"),
                    (5, "clap"),
                    (6, "clap"),
                ],
            ),
            rhythm(
                "african-bell-12-8",
                "Simple 12/8 Bell Pattern",
                "intermediate",
                60,
                twice(
                    [
                        (0, "high", True),
                        (2 * T, "high"),
                        (4 * T, "high"),
                        (5 * T, "high"),
                        (7 * T, "high"),
                        (9 * T, "high"),
                        (11 * T, "high"),
                    ]
                ),
                ts="12/8",
                subdivision=3,
            ),
            rhythm(
                "african-bell-with-bass",
                "Bell and Drum Conversation",
                "advanced",
                63,
                twice(
                    [
                        (0, "low", True),
                        (2 * T, "high"),
                        (4 * T, "high"),
                        (5 * T, "high"),
                        (2, "low"),
                        (7 * T, "high"),
                        (9 * T, "high"),
                        (11 * T, "high"),
                    ]
                ),
                ts="12/8",
                subdivision=3,
            ),
        ],
    },
    {
        "slug": "blues-rock-rnb",
        "name": "Blues, Rock & R&B",
        "description": "Steady backbeats and the classic shuffle that powers dance floors.",
        "cultural_notes": (
            "The blues was created by African Americans in the Deep South in the late 1800s and "
            "early 1900s, and its shuffle rhythm and twelve-bar form shaped nearly all popular "
            "music that followed. Rhythm and blues and rock and roll grew from it in the 1940s and "
            "50s, carrying the strong backbeat on two and four."
        ),
        "rhythms": [
            rhythm(
                "rock-backbeat",
                "Rock Backbeat",
                "beginner",
                96,
                twice([(0, "low", True), (1, "clap"), (2, "low"), (2.5, "low"), (3, "clap")]),
            ),
            rhythm(
                "rnb-clap-groove",
                "R&B Clap Groove",
                "beginner",
                84,
                twice([(0, "low", True), (1, "clap"), (3, "clap")]),
            ),
            rhythm(
                "blues-shuffle",
                "Blues Shuffle",
                "intermediate",
                84,
                twice(
                    [
                        (b + o, "low" if o == 0 else "high", o == 0 and b in (1, 3))
                        for b in range(4)
                        for o in (0, 2 * T)
                    ]
                ),
                subdivision=3,
            ),
            rhythm(
                "rock-eighths-push",
                "Rock Push",
                "intermediate",
                104,
                [
                    (0, "low", True),
                    (1, "clap"),
                    (2, "low"),
                    (2.5, "low"),
                    (3, "clap"),
                    (3.5, "low"),
                    (5, "clap"),
                    (6, "low"),
                    (7, "clap"),
                    (7.5, "high"),
                ],
            ),
            rhythm(
                "blues-shuffle-turnaround",
                "Shuffle Turnaround",
                "advanced",
                96,
                [
                    (0, "low", True),
                    (2 * T, "high"),
                    (1, "clap"),
                    (1 + 2 * T, "high"),
                    (2, "low"),
                    (2 + 2 * T, "high"),
                    (3, "clap"),
                    (4, "low", True),
                    (4 + 2 * T, "high"),
                    (5, "clap"),
                    (5 + 2 * T, "low"),
                    (6 + 2 * T, "low"),
                    (7, "clap"),
                ],
                subdivision=3,
            ),
        ],
    },
]
