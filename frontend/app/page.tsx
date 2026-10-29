import Link from "next/link";
import { ArrowDown, ArrowRight, ArrowUpRight, Check, Plus } from "lucide-react";
import styles from "./landing.module.css";

const features = [
  {
    number: "01",
    label: "FIND THE SIGNAL",
    title: "Good questions. Better direction.",
    text: "Get one useful question at a time. Resolve the details that change your build, from where data lives to what ‘done’ really means.",
    image: "dragonfly-macro-face",
    alt: "An intricately engraved dragonfly face, fragmented by digital glitches",
  },
  {
    number: "02",
    label: "KEEP YOUR MEANING",
    title: "Your words are the source.",
    text: "An intent ledger keeps your goals, decisions, and open questions together. Confirmed requirements stay connected to what you actually said.",
    image: "dragonfly-facing-pair",
    alt: "Two engraved dragonflies facing each other on a curved stem",
  },
  {
    number: "03",
    label: "MOVE WITH PURPOSE",
    title: "A brief worth building from.",
    text: "Review the understanding before you approve it. Then export a grounded build brief or hand it to the configured Claude Code adapter.",
    image: "dragonfly-head-on-flight",
    alt: "A dragonfly flying directly forward, its four wings spreading wide",
  },
];

const steps = [
  {
    title: "Say the messy version.",
    text: "A half-formed idea is enough. Type it out, or use voice input in a supported browser. No prompt engineering required.",
  },
  {
    title: "Get the important details right.",
    text: "Work through the decisions that matter. Six perspectives check your idea for gaps, conflicts, and the boundaries of the build.",
  },
  {
    title: "Lock the brief. Make your move.",
    text: "Read back the plan, make corrections, and approve it. Export the brief when it sounds like you, then take it into your build.",
  },
];

const questions = [
  {
    question: "What is Intent?",
    answer:
      "Intent is a local workspace that turns a rough software idea into an evidence-backed build brief. It asks focused questions, keeps a ledger of your decisions, and gives you a plan to review before a coding agent starts building.",
  },
  {
    question: "Do I need to know exactly what I want?",
    answer:
      "No. Start with the rough version. Intent helps you work through the details one question at a time. You can correct or change your answers as you go; new changes invalidate the previous approval and brief.",
  },
  {
    question: "Is the demo using live AI?",
    answer:
      "The default demo is scripted. It makes no model calls and uses no API credits. Its build preview is a clearly labeled prebuilt example. Live AI requires configuring your own provider credentials; it never silently falls back to demo responses.",
  },
  {
    question: "What does the coding handoff build?",
    answer:
      "You can export the approved CLAUDE.md brief, or use the configured Claude Code adapter to generate a self-contained HTML app. The current adapter does not create a running backend or cross-device synchronization. Live builds require the CLI, authentication, and explicit server configuration.",
  },
  {
    question: "Where does my data go?",
    answer:
      "Sessions are saved on your machine. In live mode, your text and intent ledger are sent to the configured model provider, and a live coding handoff shares the approved brief with the coding agent. Provider keys stay on the server.",
  },
  {
    question: "Do I need an Intent account?",
    answer:
      "No. Intent runs locally without an app account. The scripted demo works without AI credentials. Live model providers and coding tools require their own setup and may charge for usage.",
  },
];

function Brand({ footer = false }: { footer?: boolean }) {
  return (
    <Link
      href="/"
      className={footer ? styles.footerBrand : styles.brand}
      aria-label="Intent home"
    >
      <img src="/brand/dragonfly.webp" alt="" width={48} height={48} />
      <span>
        INTENT<span className={styles.brandDot}>.</span>
      </span>
    </Link>
  );
}

function OpenWorkspace({
  children = "Find your intent",
  secondary = false,
}: {
  children?: React.ReactNode;
  secondary?: boolean;
}) {
  return (
    <Link
      href="/workspace"
      className={secondary ? styles.secondaryAction : styles.primaryAction}
    >
      {children}
      <ArrowUpRight size={18} aria-hidden="true" />
    </Link>
  );
}

export default function LandingPage() {
  return (
    <div className={styles.landing} id="top">
      <a className="skip-link" href="#home-main">
        Skip to content
      </a>
      <header className={styles.header}>
        <nav className={styles.leftNav} aria-label="Main navigation">
          <a href="#why-intent">Why Intent</a>
          <a href="#how-it-works">The process</a>
        </nav>
        <Brand />
        <div className={styles.rightNav}>
          <a className={styles.faqLink} href="#faq">
            FAQs
          </a>
          <OpenWorkspace secondary>Open workspace</OpenWorkspace>
        </div>
      </header>

      <main id="home-main">
        <section className={styles.hero} aria-labelledby="hero-title">
          <div className={styles.heroCopy}>
            <p className={styles.eyebrow}>
              <span /> LESS NOISE. MORE INTENT.
            </p>
            <h1 id="hero-title">
              Build what
              <br />
              you actually
              <br />
              <span>mean.</span>
            </h1>
            <p className={styles.heroDescription}>
              Turn the idea in your head into a brief worth building. One useful
              question at a time.
            </p>
            <div className={styles.heroActions}>
              <OpenWorkspace />
              <a href="#how-it-works" className={styles.processLink}>
                See the process <ArrowDown size={15} aria-hidden="true" />
              </a>
            </div>
            <p className={styles.heroNote}>
              A LOCAL WORKSPACE. A CLEARER WAY FORWARD.
            </p>
          </div>
          <figure className={styles.heroArt}>
            <span className={styles.artTopline}>
              INTENT / FIELD NOTES NO. 001
            </span>
            <Plus className={styles.crosshair} size={23} aria-hidden="true" />
            <img
              src="/brand/dragonfly.webp"
              width={960}
              height={960}
              alt="An ivory dragonfly etched against black, its wings breaking into digital fragments"
              fetchPriority="high"
            />
            <figcaption>
              <span>PRECISION IN EVERY DIRECTION.</span>
              <span>FIG. 001 ↗</span>
            </figcaption>
          </figure>
        </section>

        <div
          className={styles.signalStrip}
          aria-label="Think clearly. Decide deliberately. Build with intent."
        >
          <span>THINK CLEARLY</span>
          <Plus size={15} aria-hidden="true" />
          <span>DECIDE DELIBERATELY</span>
          <Plus size={15} aria-hidden="true" />
          <span>BUILD WITH INTENT</span>
          <ArrowUpRight size={22} aria-hidden="true" />
        </div>

        <section
          id="why-intent"
          className={styles.featuresSection}
          aria-labelledby="features-title"
        >
          <div className={styles.sectionHeading}>
            <div>
              <p className={styles.eyebrow}>01 / BEFORE THE FIRST LINE</p>
              <h2 id="features-title">
                Clarity is your
                <br />
                <span>unfair advantage.</span>
              </h2>
            </div>
            <p>
              Every vague detail becomes a decision someone else makes for you.
              Intent brings those decisions into focus, while they’re still easy
              to change.
            </p>
          </div>
          <div className={styles.featureGrid}>
            {features.map((feature) => (
              <article className={styles.feature} key={feature.number}>
                <div className={styles.featureLabel}>
                  <span>{feature.number}</span>
                  {feature.label}
                  <ArrowUpRight size={16} aria-hidden="true" />
                </div>
                <h3>{feature.title}</h3>
                <p>{feature.text}</p>
                <div className={styles.featureArt}>
                  <img
                    src={`/brand/dragonfly-set/${feature.image}.webp`}
                    alt={feature.alt}
                    width={640}
                    height={640}
                    loading="lazy"
                  />
                </div>
              </article>
            ))}
          </div>
        </section>

        <section
          id="how-it-works"
          className={styles.processSection}
          aria-labelledby="process-title"
        >
          <div className={styles.processVisual}>
            <p className={styles.eyebrow}>02 / PURPOSE IN MOTION</p>
            <h2 id="process-title">
              From a spark.
              <br />
              To a <span>clear plan.</span>
            </h2>
            <figure className={styles.lakeArt}>
              <img
                src="/brand/dragonfly-set/dragonfly-lake-hover.webp"
                alt="An engraved dragonfly hovering over thin ripples of water"
                width={768}
                height={512}
                loading="lazy"
              />
              <figcaption>FIND THE SIGNAL. FOLLOW THROUGH.</figcaption>
            </figure>
          </div>
          <ol className={styles.steps}>
            {steps.map((step, index) => (
              <li key={step.title}>
                <span className={styles.stepIndex}>0{index + 1}</span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section
          className={styles.exampleSection}
          aria-labelledby="example-title"
        >
          <div className={styles.sectionHeading}>
            <div>
              <p className={styles.eyebrow}>03 / WHAT CLARITY LOOKS LIKE</p>
              <h2 id="example-title">
                The idea stays yours.
                <br />
                <span>The details get sharper.</span>
              </h2>
            </div>
            <p>
              No polished pitch needed. Here’s how one small question can turn
              an assumption into a decision.
            </p>
          </div>
          <div className={styles.exampleWindow}>
            <div className={styles.windowBar}>
              <span className={styles.windowDots} aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
              <span>INTENT / A CONVERSATION WITH DIRECTION</span>
              <span className={styles.exampleBadge}>ILLUSTRATIVE EXAMPLE</span>
            </div>
            <div className={styles.exampleBody}>
              <div className={styles.exampleConversation}>
                <p className={styles.microLabel}>THE ROUGH IDEA</p>
                <blockquote>
                  “A habit tracker. No login.
                  <br />
                  Saved on my phone and laptop.”
                </blockquote>
                <div className={styles.exampleQuestion}>
                  <img
                    src="/brand/dragonfly.webp"
                    alt=""
                    width={35}
                    height={35}
                  />
                  <div>
                    <p>
                      Without a login, how should your habits find you on
                      another device?
                    </p>
                    <span>A shared sync code.</span>
                  </div>
                </div>
              </div>
              <div className={styles.exampleLedger}>
                <div className={styles.ledgerTitle}>
                  <span>THE INTENT LEDGER</span>
                  <span>DECISIONS, GROUNDED</span>
                </div>
                <ul>
                  <li>
                    <Check size={15} aria-hidden="true" />
                    <div>
                      <strong>A personal habit tracker</strong>
                      <span>Source: “A habit tracker”</span>
                    </div>
                  </li>
                  <li>
                    <Check size={15} aria-hidden="true" />
                    <div>
                      <strong>No login screen</strong>
                      <span>Source: “No login”</span>
                    </div>
                  </li>
                  <li>
                    <Check size={15} aria-hidden="true" />
                    <div>
                      <strong>A shared sync code across devices</strong>
                      <span>Source: “A shared sync code”</span>
                    </div>
                  </li>
                </ul>
                <p>
                  A requirement in the brief. A clear decision for the build.
                  <br />
                  Sync implementation requires a capable build environment.
                </p>
              </div>
            </div>
            <div className={styles.exampleFoot}>
              <span>YOUR WORDS → CLEAR DECISIONS → BUILD BRIEF</span>
              <Link href="/workspace">
                Start your conversation{" "}
                <ArrowRight size={15} aria-hidden="true" />
              </Link>
            </div>
          </div>
        </section>

        <section
          id="faq"
          className={styles.faqSection}
          aria-labelledby="faq-title"
        >
          <div className={styles.faqIntro}>
            <p className={styles.eyebrow}>04 / A FEW GOOD QUESTIONS</p>
            <h2 id="faq-title">
              A little clarity,
              <br />
              <span>before you start.</span>
            </h2>
            <p>
              Know what you’re working with.
              <br />
              Then get to the good part.
            </p>
            <OpenWorkspace secondary>Explore the workspace</OpenWorkspace>
          </div>
          <div className={styles.faqList}>
            {questions.map((item, index) => (
              <details key={item.question}>
                <summary>
                  <span className={styles.faqIndex}>0{index + 1}</span>
                  <span>{item.question}</span>
                  <Plus size={19} aria-hidden="true" />
                </summary>
                <p>{item.answer}</p>
              </details>
            ))}
          </div>
        </section>

        <section className={styles.finalSection} aria-labelledby="final-title">
          <img
            className={styles.finalDragonfly}
            src="/brand/dragonfly-set/dragonfly-dorsal-spread.webp"
            alt=""
            width={600}
            height={600}
            loading="lazy"
          />
          <div className={styles.finalCopy}>
            <p className={styles.eyebrow}>YOUR NEXT MOVE STARTS HERE.</p>
            <h2 id="final-title">
              Less drift.
              <br />
              <span>More intent.</span>
            </h2>
            <OpenWorkspace>Start with your idea</OpenWorkspace>
            <p>Bring the messy version. We’ll find the signal.</p>
          </div>
        </section>
      </main>

      <footer className={styles.footer}>
        <div className={styles.footerTop}>
          <Brand footer />
          <p>Built on clarity. Driven by intent.</p>
          <nav aria-label="Footer navigation">
            <a href="#why-intent">Why Intent</a>
            <a href="#faq">FAQs</a>
            <Link href="/workspace">
              Workspace <ArrowUpRight size={13} aria-hidden="true" />
            </Link>
            <a href="#top" aria-label="Back to top">
              ↑ Top
            </a>
          </nav>
        </div>
        <div className={styles.footerBottom}>
          <span>© {new Date().getFullYear()} INTENT</span>
          <span>THINK IT. CLARIFY IT. BUILD IT.</span>
          <span>POWERED BY NEMOTRON / HANDOFF TO CLAUDE CODE</span>
        </div>
      </footer>
    </div>
  );
}
