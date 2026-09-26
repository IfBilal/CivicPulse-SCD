// Deterministic mock dataset — typed off the generated schema, never off the backend ORM.
import type { Category, Complaint, Priority, Status, TriagedBy } from "../src/api/types";

type Seed = [text: string, location: string, category: Category, priority: Priority, summary: string];

export const SEEDS: Seed[] = [
  ["Pani ka pipe burst ho gaya hai near the masjid, water flowing on road since fajr", "Street 12, G-9/1, Islamabad", "water", "high", "Burst pipe near masjid flooding the road since dawn."],
  ["Bijli ki taar gir gayi hai on the main road, bohat khatarnak hai for bachay", "Main Double Road, G-10/4, Islamabad", "electricity", "high", "Live wire fallen on main road, danger to children."],
  ["Kachra three din se nahi uthaya gaya, smell is unbearable in the gali", "Gali 7, Sector I-8/2, Islamabad", "sanitation", "normal", "Garbage uncollected for three days; strong odour."],
  ["Sarak mein bara gadha hai, two bikes already slipped yesterday raat ko", "Service Road East, F-11 Markaz", "roads", "high", "Large pothole caused two bike accidents overnight."],
  ["Street light band hai for one week, gali mein andhera, ladies feel unsafe", "Street 34, E-11/3, Islamabad", "streetlights", "normal", "Streetlight out for a week; dark and unsafe lane."],
  ["Nala block hai, barish ke baad pani ghar mein aa raha hai", "Nullah Lai side, Dhok Hassu, Rawalpindi", "sanitation", "high", "Blocked drain pushing rainwater into homes."],
  ["Load shedding schedule se zyada ho rahi hai, 10 ghante daily", "Satellite Town Block C, Rawalpindi", "electricity", "normal", "Outages exceed the published schedule, ~10h daily."],
  ["Water supply mein ganda pani aa raha hai, brown colour and smell", "Street 3, Sector H-13, Islamabad", "water", "high", "Contaminated brown, foul-smelling tap water."],
  ["Footpath tooti hui hai near school gate, bachay gir jate hain", "Model School Road, I-10/1", "roads", "normal", "Broken footpath at school gate; children tripping."],
  ["Park ki lights kharab hain, raat ko nashay wale baithtay hain", "Fatima Jinnah Park Gate 2, F-9", "streetlights", "low", "Park lights broken; area misused at night."],
  ["Transformer se chingariyan nikal rahi hain har shaam", "Mohalla Eidgah, Gujar Khan", "electricity", "high", "Transformer sparking every evening."],
  ["Tanker mafia charging double, municipal supply band hai 4 din se", "Bani Gala Road, Islamabad", "water", "normal", "Municipal supply off four days; tankers overcharging."],
  ["Awara kutton ka jhund in the street, bachon ko school jana mushkil", "Street 21, G-11/2", "other", "normal", "Pack of stray dogs making the school run unsafe."],
  ["Construction ka malba road par para hai for two weeks", "Kashmir Highway service lane, G-13", "roads", "low", "Construction debris blocking the road for two weeks."],
  ["Gutter ka dhakkan gayab hai, open manhole bohat khatarnak", "Commercial Area, I-9 Markaz", "sanitation", "high", "Missing manhole cover — open hole on a busy walkway."],
  ["Meter reading galat aa rahi hai, bill 3 guna zyada", "Sector D-12/1, Islamabad", "electricity", "low", "Meter misreading; bill tripled."],
  ["Signal ki light nahi chal rahi at the chowk, traffic jam daily", "Faizabad Interchange, Islamabad", "streetlights", "high", "Traffic signal dead at the chowk; daily jams."],
  ["Pani ki pipeline leak, poori raat pani zaya ho raha hai", "Street 9, Bahria Phase 4, Rawalpindi", "water", "normal", "Pipeline leaking water all night."],
  ["Mosquito spray nahi hua, dengue cases barh rahe hain mohallay mein", "Sadiqabad, Rawalpindi", "sanitation", "normal", "No fumigation; dengue cases rising locally."],
  ["Speed breaker bina paint ke, raat ko nazar nahi aata", "Street 5, F-8/3, Islamabad", "roads", "low", "Unpainted speed breaker invisible at night."],
  ["Noise from shaadi hall after 11 baje, har raat", "Sector G-6/4, Islamabad", "other", "low", "Wedding hall noise past 11pm nightly."],
  ["Bijli ka khamba jhuk gaya hai, kabhi bhi gir sakta hai", "Street 14, Chaklala Scheme 3", "electricity", "high", "Electric pole leaning, at risk of falling."],
  ["Sewerage overflow near the hospital gate, patients ko mushkil", "PIMS Hospital Gate 1, G-8", "sanitation", "high", "Sewage overflowing at hospital entrance."],
  ["Road carpeting adhoori chhor di gayi, gravel har jagah", "Park Road, Chak Shahzad", "roads", "normal", "Road resurfacing abandoned half-done; loose gravel."],
  ["Tube well kharab hai, poora sector bina pani ke", "Sector I-14/3, Islamabad", "water", "high", "Tube well failure; sector without water."],
  ["Gali ki light din mein bhi jalti rehti hai, bijli zaya", "Street 2, G-7/1, Islamabad", "streetlights", "low", "Streetlight stays on through the day."],
  ["Kachra kundi overflow, kawwe aur billiyan phaila rahe hain", "Tench Bhatta, Rawalpindi", "sanitation", "normal", "Overflowing garbage point being scattered by animals."],
  ["Illegal parking ki wajah se ambulance nahi guzar sakti", "Blue Area, Jinnah Avenue", "other", "normal", "Illegal parking blocking ambulance access."],
  ["Underpass mein pani khara hai after barish, gaariyan phans gayin", "Kashmir Chowk underpass, Islamabad", "roads", "high", "Flooded underpass trapping vehicles after rain."],
  ["Voltage bohat low hai, fridge aur AC nahi chal rahe", "Street 40, G-9/4, Islamabad", "electricity", "normal", "Very low voltage; appliances failing."],
  ["Pani ka pressure itna kam ke upar ki manzil tak nahi pohanchta", "Sector F-10/2, Islamabad", "water", "low", "Water pressure too low for upper floors."],
  ["Poori sarak par street lights band, highway par andhera", "Islamabad Expressway near Koral", "streetlights", "high", "Whole expressway stretch without lights."],
  ["Drain cleaning ke baad malba wahi chhor diya gaya", "Street 6, Westridge 1, Rawalpindi", "sanitation", "low", "Drain sludge left on the street after cleaning."],
  ["Zebra crossing mit gayi hai near college, students ko khatra", "Margalla Road near H-9 College", "roads", "normal", "Faded zebra crossing outside college."],
  ["Park mein jhoolay tootay hue hain, bachon ko chot lag sakti", "Lake View Park kids area", "other", "low", "Broken swings in children's play area."],
  ["Bijli ka bill aya lekin connection 2 mahine se kata hua hai", "Mohalla Rajgan, Taxila", "electricity", "low", "Billed for a connection cut two months ago."],
  ["Nalkay se pani ke saath keeray aa rahe hain", "Street 18, I-10/2, Islamabad", "water", "high", "Insects coming out with tap water."],
  ["Main road par bara darakht gir gaya hai after aandhi", "Murree Road, Committee Chowk", "roads", "high", "Large tree fallen across main road after storm."],
  ["Street light pole par bijli ka current aa raha hai, touch se jhatka", "Street 11, E-7, Islamabad", "streetlights", "high", "Streetlight pole electrified — shock on touch."],
  ["Public toilet ki safai nahi hoti, darwaza bhi toota hua", "Pir Wadhai bus stand", "sanitation", "low", "Public toilet unclean and door broken."],
  ["Mobile tower ka generator raat bhar shor karta hai", "Street 25, G-10/2, Islamabad", "other", "low", "Tower generator noisy through the night."],
  ["Hospital ke saamne road bilkul toot chuki, ambulance jhatkay khati", "Holy Family Hospital Road, Rawalpindi", "roads", "normal", "Road outside hospital badly broken."],
];

const STATUS_CYCLE: Status[] = ["open", "open", "in_progress", "open", "resolved", "in_progress", "rejected", "open"];
const PROVIDERS: TriagedBy[] = ["llm:groq", "llm:groq", "llm:gemini", "rules:fallback", "llm:groq", "rules", "llm:ollama"];

/** Deterministic UUIDv4-shaped id from an index so tests and URLs are stable. */
export function mockId(i: number): string {
  const hex = (i * 2654435761 >>> 0).toString(16).padStart(8, "0");
  return `${hex}-4c1a-4b0e-9d2f-${(i + 1).toString(16).padStart(12, "0")}`;
}

export function buildDataset(now = Date.parse("2026-09-23T09:00:00Z")): Complaint[] {
  return SEEDS.map(([text, location, category, priority, summary], i) => {
    const created = new Date(now - (i * 97 + 13) * 60_000).toISOString();
    const triaged_by = PROVIDERS[i % PROVIDERS.length]!;
    return {
      id: mockId(i),
      text,
      location,
      reporter_contact: i % 3 === 0 ? null : `+92300${String(1000000 + i * 7919).slice(-7)}`,
      category,
      priority,
      status: STATUS_CYCLE[i % STATUS_CYCLE.length]!,
      ai_summary: summary,
      triaged_by,
      triage_latency_ms: triaged_by === "rules:fallback" ? 10_000 + i * 11 : triaged_by === "rules" ? 3 + (i % 5) : 480 + ((i * 137) % 1400),
      triage_confidence: triaged_by.startsWith("llm") ? Math.round((0.72 + ((i * 7) % 27) / 100) * 100) / 100 : null,
      created_at: created,
      updated_at: created,
    };
  });
}
