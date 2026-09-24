"""Seed fixtures — `05-DATA-LAYER.md §6.2`. 36 rows, Urdu-influenced English, no real PII.

Every category has >=3 rows, every priority has >=5, `created_at` spreads across ~14 days,
`status` spans all four values so the transition demo has an `in_progress` row to resolve on
camera. `triaged_by` is always `rules` with honest single-digit latency — never a fabricated
`llm:groq` row, because that would make `/api/meta/providers` lie about provider usage.
"""

from app.domain.enums import Category, Priority, Status

# (text, location, contact, category, priority, status, day_offset, ai_summary)
SEED_ROWS: list[tuple[str, str, str | None, Category, Priority, Status, int, str]] = [
    (
        "Since fajr the water is coming out from main line near Street 12, ground floor is "
        "full, kindly send team urgent.",
        "Street 12, G-9/1, Islamabad",
        "+92 300 1234567",
        Category.WATER,
        Priority.HIGH,
        Status.OPEN,
        0,
        "Burst water main flooding ground floor.",
    ),
    (
        "Light of pole number 14 is fused from three days, at night it is total dark, ladies "
        "are afraid to walk.",
        "Pole 14, F-10 Markaz, Islamabad",
        None,
        Category.STREETLIGHTS,
        Priority.HIGH,
        Status.IN_PROGRESS,
        1,
        "Streetlight pole 14 fused, area unsafe at night.",
    ),
    (
        "Sewerage water standing in front of my gate since last Monday, smell is very bad, "
        "children are getting sick.",
        "House 22, Street 5, Chaklala Scheme 3, Rawalpindi",
        "resident.chaklala@example.com",
        Category.SANITATION,
        Priority.HIGH,
        Status.OPEN,
        2,
        "Standing sewerage water causing health risk.",
    ),
    (
        "Bijli is going every one hour in G-9 sector from morning, transformer is making loud "
        "noise, please check.",
        "G-9/2, Islamabad",
        "+92 321 9988776",
        Category.ELECTRICITY,
        Priority.NORMAL,
        Status.OPEN,
        3,
        "Frequent outages, transformer noise reported.",
    ),
    (
        "Road is broken near the chowk, big khudda there, one bike already fell yesterday, "
        "very dangerous for everyone.",
        "Committee Chowk, Rawalpindi",
        None,
        Category.ROADS,
        Priority.HIGH,
        Status.OPEN,
        4,
        "Large pothole at chowk caused an accident.",
    ),
    (
        "Water pressure is very low from two weeks in our block, upper floor is not getting "
        "any water at all.",
        "Block C, Askari 11, Lahore",
        "askari.c11@example.com",
        Category.WATER,
        Priority.NORMAL,
        Status.IN_PROGRESS,
        5,
        "Low water pressure affecting upper floors.",
    ),
    (
        "Garbage is not collected from our street for one full week now, dogs are spreading "
        "it everywhere, very unhygienic.",
        "Street 9, Model Town, Lahore",
        "+92 333 4455667",
        Category.SANITATION,
        Priority.NORMAL,
        Status.OPEN,
        6,
        "Uncollected garbage for a week.",
    ),
    (
        "Stray dogs are increasing very fast near our street, they chase children going to "
        "school, someone needs to take action before an accident.",
        "Street 16, Sector F-8, Islamabad",
        None,
        Category.OTHER,
        Priority.LOW,
        Status.OPEN,
        7,
        "Stray dog population poses safety risk to children.",
    ),
    (
        "Meter reading is wrong from last two bills, they are charging double units, already "
        "complained at office but no action.",
        "House 7, Satellite Town, Rawalpindi",
        "billing.dispute@example.com",
        Category.ELECTRICITY,
        Priority.NORMAL,
        Status.RESOLVED,
        8,
        "Disputed meter reading, overcharged units.",
    ),
    (
        "Speed breaker is needed before the school, children cross road and cars are going "
        "very fast, accident can happen any time.",
        "Near Govt Boys School, Township, Lahore",
        "+92 300 7654321",
        Category.ROADS,
        Priority.HIGH,
        Status.OPEN,
        9,
        "Speed breaker requested near school crossing.",
    ),
    (
        "Manhole cover is missing from many days on the main road, at night it is very risky, "
        "someone can fall inside.",
        "Main Boulevard, Gulberg, Lahore",
        None,
        Category.SANITATION,
        Priority.HIGH,
        Status.IN_PROGRESS,
        10,
        "Open manhole poses fall risk on main road.",
    ),
    (
        "Water tank tanker is required, our area has no supply from three days, whole "
        "mohalla is affected badly.",
        "Mohalla Iqbal, Faisalabad",
        "mohalla.iqbal@example.com",
        Category.WATER,
        Priority.HIGH,
        Status.OPEN,
        11,
        "No water supply for three days, tanker requested.",
    ),
    (
        "Wire of pole is hanging very low near our house, children can touch it, please send "
        "electrician urgent before something bad happens.",
        "Street 3, Peoples Colony, Faisalabad",
        "+92 312 1122334",
        Category.ELECTRICITY,
        Priority.HIGH,
        Status.OPEN,
        12,
        "Low-hanging live wire, urgent safety hazard.",
    ),
    (
        "Footpath is completely broken outside market, old people cannot walk properly, "
        "kindly repair as soon as possible.",
        "Main Market, Satellite Town, Rawalpindi",
        None,
        Category.ROADS,
        Priority.LOW,
        Status.OPEN,
        13,
        "Damaged footpath outside market.",
    ),
    (
        "Streetlight timer is not working, lights stay on whole day and off whole night, "
        "someone should check the sensor.",
        "Sector I-8/3, Islamabad",
        "sensor.fault@example.com",
        Category.STREETLIGHTS,
        Priority.LOW,
        Status.OPEN,
        0,
        "Streetlight timer/sensor malfunction.",
    ),
    (
        "Overflowing drain near masjid is creating very bad smell during namaz time, people "
        "are complaining daily.",
        "Near Jamia Masjid, Model Colony, Karachi",
        "+92 345 6677889",
        Category.SANITATION,
        Priority.NORMAL,
        Status.OPEN,
        1,
        "Overflowing drain causing odor near mosque.",
    ),
    (
        "There is no water in our tap since yesterday night, we called the office but no one "
        "is picking phone.",
        "Block 4, Gulshan-e-Iqbal, Karachi",
        None,
        Category.WATER,
        Priority.NORMAL,
        Status.OPEN,
        2,
        "No tap water since previous night, office unreachable.",
    ),
    (
        "Transformer blast hua kal raat, area mein andhera hai, bohat mushkil ho rahi hai "
        "bachon ko lekar.",
        "Sector 11-C, North Karachi",
        "transformer.blast@example.com",
        Category.ELECTRICITY,
        Priority.HIGH,
        Status.IN_PROGRESS,
        3,
        "Transformer failure caused area-wide blackout.",
    ),
    (
        "Road digging work started one month ago for pipeline but never finished, whole "
        "street is dusty and cars get stuck daily.",
        "Street 18, DHA Phase 2, Karachi",
        "+92 300 2233445",
        Category.ROADS,
        Priority.NORMAL,
        Status.OPEN,
        4,
        "Unfinished pipeline excavation blocking street.",
    ),
    (
        "Trash bin near corner shop is always overflowing, nobody empties it, flies are "
        "everywhere near the food stalls.",
        "Corner Shop, Liaquatabad, Karachi",
        None,
        Category.SANITATION,
        Priority.LOW,
        Status.OPEN,
        5,
        "Overflowing public trash bin near food stalls.",
    ),
    (
        "Two streetlights near bus stop not working from long time, girls coming from "
        "college feel unsafe waiting in dark.",
        "Bus Stop, University Road, Peshawar",
        "safety.concern@example.com",
        Category.STREETLIGHTS,
        Priority.HIGH,
        Status.OPEN,
        6,
        "Non-functional streetlights near bus stop, safety concern.",
    ),
    (
        "Low voltage problem is damaging our home appliances, fridge already got damaged, "
        "please send someone to check the line.",
        "House 45, Hayatabad Phase 3, Peshawar",
        "+92 333 9988001",
        Category.ELECTRICITY,
        Priority.NORMAL,
        Status.OPEN,
        7,
        "Persistent low voltage damaging appliances.",
    ),
    (
        "Bridge ka railing toot gaya hai ek taraf se, log darte hain cross karte waqt, "
        "please fix as soon as possible.",
        "Canal Bridge, Township, Lahore",
        None,
        Category.ROADS,
        Priority.HIGH,
        Status.OPEN,
        8,
        "Broken bridge railing poses fall risk.",
    ),
    (
        "Illegal parking of trucks is blocking half the road every night near the market, "
        "residents cannot even bring their cars out.",
        "Jinnah Park, F-9, Islamabad",
        "park.facilities@example.com",
        Category.OTHER,
        Priority.LOW,
        Status.OPEN,
        9,
        "Illegal truck parking obstructing road access.",
    ),
    (
        "New water connection request pending from two months, office keeps saying next "
        "week but nothing happens.",
        "Street 30, DHA Phase 1, Islamabad",
        "+92 321 5544332",
        Category.WATER,
        Priority.LOW,
        Status.OPEN,
        10,
        "New water connection request delayed two months.",
    ),
    (
        "Meter box is sparking sometimes at night, very scary, neighbours also noticed same "
        "thing, please send technician urgent.",
        "Flat 12B, Clifton Block 5, Karachi",
        None,
        Category.ELECTRICITY,
        Priority.HIGH,
        Status.OPEN,
        11,
        "Sparking meter box, urgent electrical hazard.",
    ),
    (
        "Speed camera pole is bent since the storm, it might fall on the road, cars are "
        "passing very close to it.",
        "Ring Road, Peshawar",
        "storm.damage@example.com",
        Category.ROADS,
        Priority.NORMAL,
        Status.OPEN,
        12,
        "Storm-damaged pole leaning over roadway.",
    ),
    (
        "Drain cover slab is broken into pieces outside our house, very dangerous for "
        "children playing in the street.",
        "Street 6, Wapda Town, Lahore",
        "+92 300 6677123",
        Category.SANITATION,
        Priority.HIGH,
        Status.REJECTED,
        13,
        "Broken drain cover slab, hazard for children.",
    ),
    (
        "Water tanker mafia is selling water very expensive because official supply stopped "
        "completely, poor families are suffering most.",
        "Orangi Town, Karachi",
        None,
        Category.WATER,
        Priority.NORMAL,
        Status.OPEN,
        0,
        "Official supply stopped, exploitative tanker pricing.",
    ),
    (
        "Streetlight pole fell down after yesterday's wind storm, wires are open on the "
        "ground, very dangerous please attend fast.",
        "Sector 5-D, North Nazimabad, Karachi",
        "urgent.hazard@example.com",
        Category.STREETLIGHTS,
        Priority.HIGH,
        Status.OPEN,
        1,
        "Fallen streetlight pole with exposed wiring.",
    ),
    (
        "Voltage fluctuation is burning bulbs every few days in whole street, electrician "
        "says main line ka fault hai.",
        "Street 14, Samanabad, Lahore",
        "+92 312 8899001",
        Category.ELECTRICITY,
        Priority.LOW,
        Status.OPEN,
        2,
        "Voltage fluctuation damaging fixtures street-wide.",
    ),
    (
        "Noise from generator of nearby wedding hall runs whole night, kids cannot sleep "
        "and study for exams, please take action.",
        "Near Cadet College Road, Hasilpur",
        None,
        Category.OTHER,
        Priority.LOW,
        Status.OPEN,
        3,
        "Nighttime generator noise from wedding hall disturbing residents.",
    ),
    (
        "Sewerage line burst under the road, dirty water is mixing with fresh water supply "
        "pipe, we are worried about disease.",
        "Street 21, Latifabad, Hyderabad",
        "health.concern@example.com",
        Category.SANITATION,
        Priority.HIGH,
        Status.IN_PROGRESS,
        4,
        "Sewerage line contaminating fresh water supply.",
    ),
    (
        "Water quality has become very bad from last week, smell and colour both are wrong, "
        "we stopped drinking it directly.",
        "Sector 6-B, Qasimabad, Hyderabad",
        "+92 345 1029384",
        Category.WATER,
        Priority.HIGH,
        Status.OPEN,
        5,
        "Water quality degraded, discoloration and odor.",
    ),
    (
        "Pole number 22 ka light lagta continuous flicker karti hai, transformer se aawaz "
        "bhi aa rahi hai, please check karain.",
        "Pole 22, Latifabad Unit 8, Hyderabad",
        None,
        Category.STREETLIGHTS,
        Priority.NORMAL,
        Status.OPEN,
        6,
        "Flickering streetlight, possible transformer fault.",
    ),
    (
        "Load shedding schedule is not being followed, we get less hours than promised, "
        "small shopkeepers are losing business badly.",
        "Main Bazaar, Sahiwal",
        "shopkeepers.union@example.com",
        Category.ELECTRICITY,
        Priority.NORMAL,
        Status.OPEN,
        7,
        "Load shedding schedule not honored, business impact.",
    ),
]
