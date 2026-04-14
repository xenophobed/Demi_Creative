import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import useDailyTaskStore from "@/store/useDailyTaskStore";

interface InspirationDailyProps {
  className?: string;
  onTear?: () => void;
  isAuthenticated?: boolean;
  /** When provided, overrides the built-in day-of-year rotation. */
  content?: DailyContent;
}

export interface DailyContent {
  headline: string;
  body: string;
  illustration: string;
  weather: string;
  weatherEmoji: string;
  miniAd: string;
  /** When set, a "Try This!" CTA button is rendered linking to the matching creation tool. */
  cta_type?: "draw" | "story" | "explore";
  cta_route?: "/upload" | "/interactive" | "/news";
  creative_prompt?: string;
}

const DAILY_CONTENT: DailyContent[] = [
  {
    headline: "Flying Fish Spotted!",
    body: "Breaking news from the South Pacific: a school of rainbow-colored flying fish soared over an entire island yesterday. Witnesses say their wings were covered in rainbow patterns. Scientists are calling on young artists everywhere to draw them as a precious scientific record.",
    illustration: "🐟✨",
    weather: "Sunny, turning to cotton candy",
    weatherEmoji: "☀️",
    miniAd: "🖍️ Rainbow crayons: buy one get one half off",
  },
  {
    headline: "Cotton Candy Clouds Incoming!",
    body: "Breaking news: the weather bureau has issued a sweet alert. Due to warm air currents, all clouds in the city will turn into cotton candy today. Residents are advised to bring long poles for collecting. Strawberry flavor is rare — first come, first served.",
    illustration: "☁️🍬",
    weather: "Cloudy, turning sweet",
    weatherEmoji: "☁️",
    miniAd: "🎒 Flying backpacks now on pre-order",
  },
  {
    headline: "Undersea Castle Opens to Visitors",
    body: "Breaking news: the Mermaid Queen has signed a royal decree opening the Undersea Crystal Palace to land children. Entry requirement: submit a drawing of your dream undersea castle. The best design will be built into a real coral sculpture.",
    illustration: "🏰🌊",
    weather: "Gentle sea breeze",
    weatherEmoji: "🌊",
    miniAd: "🫧 Waterproof drawing paper just arrived",
  },
  {
    headline: "Dinosaur Chef Hits a Snag",
    body: 'Breaking news: the Natural History Museum confirms a revived T-Rex has passed its chef exam but cannot flip a pan because its arms are too short. It is now seeking solutions worldwide — the most practical invention wins the "Best Dino Assistant" medal.',
    illustration: "🦕👨‍🍳",
    weather: "Partly volcanic ash",
    weatherEmoji: "🌋",
    miniAd: "📏 Dino arm extenders selling fast",
  },
  {
    headline: "Star Train Departing Tonight!",
    body: "Breaking news: the Milky Way Railway Company announces the express train to the North Star departs tonight. The train has 108 starlight carriages, stopping at Moon Station and Mars Station. How to get tickets: draw the coolest train and give it to the conductor.",
    illustration: "🚂⭐",
    weather: "Starry skies",
    weatherEmoji: "🌙",
    miniAd: "🔭 Mini telescopes: buy one get one free",
  },
  {
    headline: "Pet Fashion Week Begins!",
    body: "Breaking news: the 3rd Global Pet Fashion Week kicked off in Central Park today. This year's theme is \"Superheroes\" — all competing pets must wear capes designed by their young owners. Grand prize: a year's supply of fish treats.",
    illustration: "🦸‍♀️🐕",
    weather: "Perfect runway weather",
    weatherEmoji: "✨",
    miniAd: "🧵 DIY pet cape kit available",
  },
  {
    headline: "Rainbow Slide Breaks World Record",
    body: "Breaking news: the engineering team announces the mega slide from the top of a rainbow down to the marshmallow pond is complete. At 7.7 km long, it sets a new world record. Test riders report: a bit toasty on the bottom, but totally worth it.",
    illustration: "🌈🎢",
    weather: "Rainbow showers",
    weatherEmoji: "🌈",
    miniAd: "🩳 Heat-proof slide pants, limited edition",
  },
  {
    headline: "Magic Wand Malfunction Alert",
    body: "Breaking news: the School of Magic has issued an urgent notice. Grandpa Wizard's century-old wand has a rare glitch — it can only turn drawings on paper into real objects. The school advises kids to draw carefully. Last time someone drew a T-Rex, things got chaotic.",
    illustration: "🪄✨",
    weather: "Occasional magic lightning",
    weatherEmoji: "⚡",
    miniAd: "📒 Anti-magic drawing paper now in stock",
  },
  {
    headline: "Moon Amusement Park Grand Opening",
    body: "Breaking news: after three years of construction, the Moon Fun Valley is officially open. With gravity only one-sixth of Earth's, a single jump sends you three meters high, and the Ferris wheel takes half an hour per revolution. Park staff remind visitors: buckle up and don't fly too high.",
    illustration: "🌙🎠",
    weather: "Moon: zero-gravity clear",
    weatherEmoji: "🌙",
    miniAd: "🧑‍🚀 Space travel insurance, only $9.99",
  },
  {
    headline: "Cat Hat Design Contest",
    body: "Breaking news: the Global Cat Federation announces the first-ever hat design contest. The judges are three senior Ragdoll cats. Scoring criteria: cuteness 60%, practicality 20%, cat-treat bribery 20%. Submission deadline: tomorrow.",
    illustration: "🐱🎩",
    weather: "Light cat fur flurries",
    weatherEmoji: "🐱",
    miniAd: "🧶 Cat yarn balls on sale",
  },
  {
    headline: "Candy House Emergency Repairs",
    body: "Breaking news: the Fairytale Town building department announces the chocolate door of the candy house on Third Street has melted due to high temperatures. A temporary cookie door is in place. Urgently seeking a young architect to submit a new design — must be pretty, tasty, and heat-proof.",
    illustration: "🍭🏠",
    weather: "Hot enough to melt chocolate",
    weatherEmoji: "🌡️",
    miniAd: "🍫 Heat-resistant chocolate bricks invented",
  },
  {
    headline: "Baby Dragon's Big Move Sparks Debate",
    body: 'Breaking news: a three-year-old fire dragon has decided to move from an iceberg to a volcano, saying it "just wants to live somewhere warmer." Neighbors worry its sneezes could start fires and suggest it learns to control its flames first. The little dragon promises to practice hard.',
    illustration: "🐉🏡",
    weather: "Occasional fire-breathing",
    weatherEmoji: "🔥",
    miniAd: "🧯 Fireproof curtains on sale",
  },
  {
    headline: "Juice Ocean Stuns Scientists",
    body: "Breaking news: the Ocean Research Institute confirms that a section of the Arctic Ocean has turned into fresh-squeezed orange juice. Scientists believe it's linked to a giant underground orange vein. Coastal residents say breakfast is easier now, but the fish are not happy.",
    illustration: "🧃🏊",
    weather: "Orange juice showers expected",
    weatherEmoji: "🍊",
    miniAd: "🥤 Bottled ocean orange juice available",
  },
  {
    headline: "Penguin Ice Skating Champion Crowned",
    body: "Breaking news: the Antarctic Winter Skating Championship has concluded. Emperor penguin Pinky, wearing pink skates, won with a flawless triple axel. After the event, Pinky shared the secret to victory: eating ten fish a day to keep up energy.",
    illustration: "🐧⛸️",
    weather: "-40 degrees, perfect for skating",
    weatherEmoji: "❄️",
    miniAd: "⛸️ Penguin-brand ice skates now available",
  },
  {
    headline: "Floating Garden Appears Downtown",
    body: "Breaking news: at six this morning, a garden in the city center slowly rose into the air and is now hovering at 200 meters. The gardener calmly explains he used too much magic fertilizer last night. Residents have switched to hot air balloons for their morning walks.",
    illustration: "🌺☁️",
    weather: "Floating pollen",
    weatherEmoji: "🌸",
    miniAd: "🎈 Personal hot air balloon, monthly rental deal",
  },
  {
    headline: "Frog King Coronation Ceremony",
    body: "Breaking news: a grand coronation was held at the Lily Pond. The new Frog King promised in his inaugural speech to give every frog a lily pad with a balcony. But the crown isn't finished yet — urgently seeking a young designer to help!",
    illustration: "🐸👑",
    weather: "Pond breeze",
    weatherEmoji: "🍃",
    miniAd: "👑 Tiny gold crowns, custom-made",
  },
  {
    headline: "Tree Sprite Seeks Roommate",
    body: 'Breaking news: a sprite living in a thousand-year-old oak tree has posted a roommate wanted ad. Requirements: can draw, loves storytelling, no snoring. Rent: three acorns per month. The sprite says the last roommate was a woodpecker — "way too noisy."',
    illustration: "🧚‍♂️🌳",
    weather: "Forest mist",
    weatherEmoji: "🌲",
    miniAd: "🏡 Treehouse renovations — call us",
  },
  {
    headline: "Color-Changing Forest Mystery Solved",
    body: "Breaking news: after three years of research, botanists have finally discovered the secret of the mysterious color-changing forest. A group of playful chameleons rubbed their colors onto tree trunks while playing hide-and-seek. The forestry bureau says they won't stop them because it looks amazing.",
    illustration: "🌲🎨",
    weather: "Kaleidoscope skies",
    weatherEmoji: "🎨",
    miniAd: "🎨 Forest sketching trips, sign up now",
  },
  {
    headline: "Musical Bridge Opens to Traffic",
    body: "Breaking news: the Musical Note Bridge, two years in the making, opened today. Every step produces a musical note — running plays rock music, walking plays classical. Bridge management reminds everyone: no tap dancing on the bridge. It nearly collapsed last week.",
    illustration: "🎶🌉",
    weather: "Melodic breezes",
    weatherEmoji: "🎵",
    miniAd: "🎹 Portable piano keyboard on sale",
  },
  {
    headline: "The Sun Officially Requests Sunglasses",
    body: 'Breaking news: the Sun filed a formal request with the Cosmic Management Bureau today: "I have been working for 3.8 billion years and was never issued protective eyewear. I strongly demand a proper pair of sunglasses." The bureau is now collecting design proposals worldwide.',
    illustration: "☀️😎",
    weather: "Super sunny (Sun is complaining)",
    weatherEmoji: "☀️",
    miniAd: "🕶️ Giant custom sunglasses service",
  },
  {
    headline: "Lollipop Trees: Bumper Harvest!",
    body: "Breaking news: the Magic Farm celebrates a lollipop tree bumper harvest — this year's yield is triple last year's. Strawberry flavor is the most popular; rainbow flavor is the rarest. The farmer reminds pickers: wash your hands before eating — there's magic sugar dust on the trees.",
    illustration: "🍭🌴",
    weather: "Sweetness overload",
    weatherEmoji: "🍬",
    miniAd: "🪣 Lollipop picking baskets, just in",
  },
];

function getDailyContent(): DailyContent {
  const now = new Date();
  const start = new Date(now.getFullYear(), 0, 0);
  const dayOfYear = Math.floor(
    (now.getTime() - start.getTime()) / (1000 * 60 * 60 * 24),
  );
  return DAILY_CONTENT[dayOfYear % DAILY_CONTENT.length];
}

function formatDate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const day = now.getDate();
  const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return `${weekdays[now.getDay()]}, ${months[now.getMonth()]} ${day}, ${year}`;
}

function getEditionNumber(): number {
  const launch = new Date(2026, 0, 1);
  return (
    Math.floor((Date.now() - launch.getTime()) / (1000 * 60 * 60 * 24)) + 1
  );
}

const serif = '"Georgia", "Noto Serif", "Times New Roman", serif';

export default function InspirationDaily({
  className = "",
  onTear,
  isAuthenticated,
  content: contentProp,
}: InspirationDailyProps) {
  const canClaimToday = useDailyTaskStore((s) => s.canClaimToday());
  const canClaim = isAuthenticated && canClaimToday;
  const content = contentProp ?? getDailyContent();
  const dateStr = formatDate();
  const edition = getEditionNumber();

  const muted = !isAuthenticated || !canClaim;

  if (!isAuthenticated) {
    return (
      <div
        className={`relative overflow-hidden rounded-card border border-[#f2d2b7] shadow-[0_12px_28px_rgba(255,158,102,0.18)] ${className}`}
        style={{
          background:
            "linear-gradient(145deg, #fffaf2 0%, #fff3f6 45%, #eef9ff 100%)",
          color: "#5a3f2d",
        }}
      >
        <div
          className="absolute inset-0 pointer-events-none opacity-[0.08]"
          style={{
            backgroundImage:
              "radial-gradient(circle at 12px 12px, rgba(255, 179, 138, 0.35) 2px, transparent 2px)",
            backgroundSize: "22px 22px",
          }}
        />
        <div className="absolute -top-10 -right-8 h-28 w-28 rounded-full bg-[#ffd9c2] blur-2xl" />
        <div className="absolute -bottom-12 -left-10 h-32 w-32 rounded-full bg-[#cfeeff] blur-2xl" />

        <div className="relative p-5 sm:p-6">
          <div className="flex items-center justify-center gap-2">
            <span className="inline-flex items-center rounded-full border border-[#efc7a7] bg-white/80 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[#9b6840]">
              Kawaii Daily Reward
            </span>
          </div>

          <div className="mt-3 flex justify-center gap-2 text-xl">
            <motion.span
              animate={{ y: [0, -3, 0], rotate: [0, 8, -8, 0] }}
              transition={{
                duration: 3.2,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            >
              🐰
            </motion.span>
            <motion.span
              animate={{ y: [0, -3, 0], rotate: [0, -8, 8, 0] }}
              transition={{
                duration: 3.2,
                repeat: Infinity,
                ease: "easeInOut",
                delay: 0.4,
              }}
            >
              ⭐
            </motion.span>
            <motion.span
              animate={{ y: [0, -3, 0], rotate: [0, 8, -8, 0] }}
              transition={{
                duration: 3.2,
                repeat: Infinity,
                ease: "easeInOut",
                delay: 0.8,
              }}
            >
              🍓
            </motion.span>
          </div>

          <h3
            className="mt-3 text-center text-2xl sm:text-3xl font-black tracking-wide"
          >
            Daily Reward Locked
          </h3>
          <p
            className="mt-1 text-center text-[11px] text-[#8b6a52]"
          >
            Edition {edition} · {dateStr}
          </p>

          <div className="mt-4 rounded-2xl border border-[#efc7a7] bg-white/85 px-4 py-4 text-center shadow-sm">
            <div className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-full border-2 border-[#f2c7a2] bg-[#fff5ea] shadow-inner">
              <span className="text-3xl">🔒</span>
            </div>
            <p
              className="mt-2 text-sm leading-relaxed text-[#775a45]"
            >
              Please log in first. Only logged-in users can claim daily rewards.
            </p>
          </div>

          <div className="mt-3 grid grid-cols-3 gap-2 text-[11px]">
            <div className="rounded-xl border border-[#f0cfb4] bg-[#fff7ef] py-1.5 text-center text-[#7d5b42]">
              1 star/day
            </div>
            <div className="rounded-xl border border-[#f0cfb4] bg-[#fff7ef] py-1.5 text-center text-[#7d5b42]">
              Streak bonus
            </div>
            <div className="rounded-xl border border-[#f0cfb4] bg-[#fff7ef] py-1.5 text-center text-[#7d5b42]">
              Profile bonus
            </div>
          </div>

          <div className="mt-4 flex justify-center">
            <motion.div
              whileHover={{ scale: 1.03, y: -1 }}
              whileTap={{ scale: 0.98 }}
            >
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 rounded-full border border-[#e9b995] bg-gradient-to-r from-[#ffb58b] to-[#ff8f8f] px-4 py-2 text-xs font-semibold text-white shadow-[0_4px_10px_rgba(255,143,143,0.35)] hover:opacity-90 transition-opacity"
              >
                <span>✨</span>
                <span>Log In to Claim</span>
              </Link>
            </motion.div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`relative overflow-hidden rounded-card ${
        muted ? "opacity-60" : ""
      } ${className}`}
      style={{
        background: muted ? "#eae7e1" : "#FDF8F0",
        color: muted ? "#999" : "#2a2a2a",
      }}
    >
      {/* Subtle paper grain */}
      {!muted && (
        <div
          className="absolute inset-0 pointer-events-none opacity-[0.035]"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='200' height='200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='200' height='200' filter='url(%23n)'/%3E%3C/svg%3E")`,
          }}
        />
      )}

      {/* =========== MASTHEAD — tear zone =========== */}
      <div
        className="relative select-none"
        onClick={canClaim ? onTear : undefined}
        style={canClaim ? { cursor: "grab" } : undefined}
      >
        {/* Thick top rule */}
        <div className={`h-[3px] ${muted ? "bg-gray-300" : "bg-gray-900"}`} />
        <div
          className={`h-[1px] mt-[2px] mx-3 ${muted ? "bg-gray-200" : "bg-gray-900/40"}`}
        />

        <div className="px-4 pt-2 pb-1 text-center">
          {/* Date row */}
          <div
            className="flex items-center justify-between"
            style={{ fontSize: 9, fontFamily: serif }}
          >
            <span>Edition {edition}</span>
            <span>{dateStr}</span>
            <span>Daily edition</span>
          </div>

          {/* Thin rule */}
          <div
            className={`border-t my-1.5 ${muted ? "border-gray-200" : "border-gray-900/20"}`}
          />

          {/* Nameplate */}
          <h3
            className="text-3xl sm:text-4xl font-black tracking-[0.4em] leading-none py-1"
            style={{ fontFamily: serif }}
          >
            Inspiration Daily
          </h3>

          {/* English subtitle */}
          <p
            className="text-[8px] sm:text-[9px] tracking-[0.35em] uppercase mt-0.5"
            style={{ opacity: muted ? 0.4 : 0.35, fontFamily: serif }}
          >
            The Inspiration Daily · For Young Creators
          </p>

          {/* Double rule */}
          <div className="mt-2 mb-1">
            <div
              className={`border-t-[2.5px] ${muted ? "border-gray-300" : "border-gray-900"}`}
            />
            <div
              className={`border-t mt-[2px] ${muted ? "border-gray-200" : "border-gray-900/50"}`}
            />
          </div>
        </div>

        {/* Tear hint */}
        {canClaim && (
          <div className="relative h-6 flex items-center px-4">
            <div className="flex-1 border-t-2 border-dashed border-primary/25" />
            <motion.span
              className="absolute right-4 flex items-center gap-1 text-[10px] text-primary/50"
              animate={{ x: [0, 6, 0] }}
              transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
            >
              ✂️ Tear to collect stars
            </motion.span>
          </div>
        )}
      </div>

      {/* =========== CONTENT AREA =========== */}
      {canClaim ? (
        <div className="px-4 pb-3">
          {/* --- Headline banner --- */}
          <div className="flex gap-3 items-start">
            {/* Main headline + body */}
            <div className="flex-1 min-w-0">
              <h4
                className="text-lg sm:text-xl font-bold leading-tight"
                style={{ fontFamily: serif }}
              >
                {content.headline}
              </h4>
              <div className={`border-t my-1.5 border-gray-900/10`} />
              <p
                className="text-xs sm:text-sm leading-relaxed text-gray-700"
                style={{ fontFamily: serif, textAlign: "justify" }}
              >
                <span
                  className="text-2xl font-bold float-left mr-1 leading-[1] text-primary/80"
                  style={{ fontFamily: serif }}
                >
                  {content.body[0]}
                </span>
                {content.body.slice(1)}
              </p>
            </div>

            {/* Illustration column with vertical rule */}
            <div className="flex-shrink-0 flex items-stretch">
              <div className={`w-px self-stretch bg-gray-900/10 mr-2.5`} />
              <div className="flex flex-col items-center justify-center w-14 sm:w-16">
                <motion.span
                  className="text-4xl sm:text-5xl block"
                  animate={{ y: [0, -3, 0] }}
                  transition={{
                    duration: 3,
                    repeat: Infinity,
                    ease: "easeInOut",
                  }}
                >
                  {content.illustration}
                </motion.span>
              </div>
            </div>
          </div>

          {/* --- CTA button (only when InspirationCard data provides cta_type) --- */}
          {content.cta_type && content.cta_route && (
            <div className="mt-3 flex justify-center">
              <motion.div
                whileHover={{ scale: 1.05, y: -1 }}
                whileTap={{ scale: 0.95 }}
              >
                <Link
                  to={content.cta_route}
                  state={
                    content.creative_prompt
                      ? { inspirationPrompt: content.creative_prompt }
                      : undefined
                  }
                  className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-amber-400 via-orange-400 to-pink-400 px-5 py-2 text-sm font-bold text-white shadow-[0_4px_14px_rgba(251,146,60,0.4)] transition-shadow hover:shadow-[0_6px_20px_rgba(251,146,60,0.55)]"
                >
                  <span>
                    {content.cta_type === "draw" && "🎨"}
                    {content.cta_type === "story" && "📖"}
                    {content.cta_type === "explore" && "🌍"}
                  </span>
                  <span>Try This!</span>
                </Link>
              </motion.div>
            </div>
          )}

          {/* --- Bottom row: weather + mini-ad --- */}
          <div className="mt-2.5">
            <div className={`border-t border-gray-900/10 mb-2`} />
            <div
              className="flex items-center justify-between text-[10px]"
              style={{ fontFamily: serif }}
            >
              {/* Weather box */}
              <div className="flex items-center gap-1">
                <span>{content.weatherEmoji}</span>
                <span className="text-gray-500">
                  Today's weather: {content.weather}
                </span>
              </div>

              {/* Vertical divider */}
              <div className="w-px h-3 bg-gray-900/10 mx-2" />

              {/* Mini classified ad */}
              <div className="text-gray-400 truncate">{content.miniAd}</div>
            </div>
          </div>
        </div>
      ) : (
        /* Claimed state */
        <div className="text-center px-4 py-5">
          <span className="text-3xl">📰</span>
          <p
            className="text-sm text-gray-400 mt-2 font-semibold"
            style={{ fontFamily: serif }}
          >
            Today's paper read
          </p>
          <p
            className="text-[11px] text-gray-400 mt-0.5"
            style={{ fontFamily: serif }}
          >
            Stay tuned for tomorrow's edition
          </p>
        </div>
      )}

      {/* Bottom rules */}
      <div
        className={`h-px mx-3 ${muted ? "bg-gray-200" : "bg-gray-900/30"}`}
      />
      <div
        className={`h-[2.5px] mt-[2px] ${muted ? "bg-gray-300" : "bg-gray-900"}`}
      />
    </div>
  );
}
