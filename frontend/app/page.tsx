import Link from "next/link";
import { ArrowUpRight, Plus } from "lucide-react";
import styles from "./landing.module.css";

const features = [
  {
    title: "Focus",
    text: "One question. The decision that matters.",
    image: "dragonfly-macro-face",
    alt: "An engraved dragonfly face with fragmented edges",
  },
  {
    title: "Vision",
    text: "Your goals, sharpened into a plan.",
    image: "dragonfly-facing-pair",
    alt: "Two engraved dragonflies facing each other",
  },
  {
    title: "Build",
    text: "Approve the brief. Make it real.",
    image: "dragonfly-head-on-flight",
    alt: "An engraved dragonfly in flight",
  },
];

const steps = [
  { title: "Say it.", text: "Start with your idea." },
  { title: "Shape it.", text: "Resolve what matters." },
  { title: "Build it.", text: "Approve. Export. Build." },
];

const questions = [
  {
    question: "What is Intent?",
    answer:
      "A local idea-to-brief workspace. Answer focused questions, review the plan, then build.",
  },
  {
    question: "Is the demo live?",
    answer:
      "No. Demo responses and previews are scripted, with no model calls. Live AI requires your own provider credentials.",
  },
  {
    question: "What can it build?",
    answer:
      "The current adapter generates self-contained HTML apps. Backends and cross-device sync need a separate build environment.",
  },
  {
    question: "Where is my data?",
    answer:
      "Saved locally. Live mode sends your text and plan to configured AI providers; coding handoffs share the approved brief.",
  },
];

function Brand({ footer = false }: { footer?: boolean }) {
  return (
    <Link
      href="/"
      className={footer ? styles.footerBrand : styles.brand}
      aria-label="Intent home"
    >
      <img
        src="/brand/dragonfly-transparent.webp"
        alt=""
        width={48}
        height={48}
      />
      <span className={styles.wordmark}>
        <img src="/brand/intent-wordmark.svg" alt="" width={386} height={200} />
      </span>
    </Link>
  );
}

function OpenWorkspace({ secondary = false }: { secondary?: boolean }) {
  return (
    <Link
      href="/workspace"
      className={secondary ? styles.secondaryAction : styles.primaryAction}
    >
      {secondary ? "Workspace" : "Start"}
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
          <a href="#why-intent">Intent</a>
          <a href="#how-it-works">Process</a>
        </nav>
        <Brand />
        <div className={styles.rightNav}>
          <a className={styles.faqLink} href="#faq">
            FAQs
          </a>
          <OpenWorkspace secondary />
        </div>
      </header>

      <main id="home-main">
        <section className={styles.hero} aria-labelledby="hero-title">
          <div className={styles.heroCopy}>
            <h1 id="hero-title">
              Build what
              <br />
              <span>you mean.</span>
            </h1>
            <p className={styles.heroDescription}>
              Turn your idea into a build brief.
            </p>
            <div className={styles.heroActions}>
              <OpenWorkspace />
            </div>
          </div>
          <figure className={styles.heroArt}>
            <img
              src="/brand/dragonfly-transparent.webp"
              width={960}
              height={960}
              alt="An ivory dragonfly with glitched wings on black"
              fetchPriority="high"
            />
          </figure>
        </section>

        <section
          id="why-intent"
          className={styles.featuresSection}
          aria-labelledby="features-title"
        >
          <h2 id="features-title" className="sr-only">
            Intent
          </h2>
          <div className={styles.featureGrid}>
            {features.map((feature) => (
              <article className={styles.feature} key={feature.title}>
                <h3>{feature.title}</h3>
                <p>{feature.text}</p>
                <div className={styles.featureArt}>
                  <img
                    src={`/brand/dragonfly-set/${feature.image}-transparent.webp`}
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
            <p className={styles.sectionEyebrow}>01 / The process</p>
            <h2 id="process-title">
              Noise to
              <br />
              <span>signal.</span>
            </h2>
            <figure className={styles.lakeArt}>
              <div className={styles.artOrbit} aria-hidden="true" />
              <img
                src="/brand/dragonfly-set/dragonfly-lake-hover-transparent.webp"
                alt="An engraved dragonfly hovering above water"
                width={768}
                height={512}
                loading="lazy"
              />
              <figcaption>A thought, taking shape.</figcaption>
            </figure>
          </div>
          <div className={styles.processFlow}>
            <p className={styles.processLead}>
              Big ideas.
              <br />
              Clear next moves.
            </p>
            <ol className={styles.steps}>
              {steps.map((step, index) => (
                <li key={step.title}>
                  <span className={styles.stepIndex} aria-hidden="true">
                    0{index + 1}
                  </span>
                  <div>
                    <h3>{step.title}</h3>
                    <p>{step.text}</p>
                  </div>
                  <ArrowUpRight
                    className={styles.stepArrow}
                    size={28}
                    aria-hidden="true"
                  />
                </li>
              ))}
            </ol>
            <Link href="/workspace" className={styles.processLink}>
              Put your idea in motion{" "}
              <ArrowUpRight size={20} aria-hidden="true" />
            </Link>
          </div>
        </section>

        <section
          id="faq"
          className={styles.faqSection}
          aria-labelledby="faq-title"
        >
          <div className={styles.faqIntro}>
            <p className={styles.sectionEyebrow}>02 / A little clarity</p>
            <h2 id="faq-title">
              Good
              <br />
              questions.
            </h2>
            <p className={styles.faqDescription}>
              A few things worth knowing
              <br />
              before you begin.
            </p>
            <ArrowUpRight
              className={styles.faqIntroArrow}
              size={48}
              strokeWidth={1}
              aria-hidden="true"
            />
            <span className={styles.faqMark} aria-hidden="true">
              ?
            </span>
          </div>
          <div className={styles.faqList}>
            {questions.map((item, index) => (
              <details key={item.question}>
                <summary>
                  <span className={styles.faqNumber} aria-hidden="true">
                    0{index + 1}
                  </span>
                  <span className={styles.faqQuestion}>{item.question}</span>
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
            src="/brand/dragonfly-set/dragonfly-dorsal-spread-transparent.webp"
            alt=""
            width={600}
            height={600}
            loading="lazy"
          />
          <div className={styles.finalCopy}>
            <h2 id="final-title">
              With
              <br />
              <span>intent.</span>
            </h2>
            <OpenWorkspace />
          </div>
        </section>
      </main>

      <footer className={styles.footer}>
        <div className={styles.footerTop}>
          <Brand footer />
          <nav aria-label="Footer navigation">
            <a href="#faq">FAQs</a>
            <Link href="/workspace">Workspace</Link>
            <a href="#top" aria-label="Back to top">
              ↑ Top
            </a>
          </nav>
        </div>
        <div className={styles.footerBottom}>
          <span>© {new Date().getFullYear()} INTENT</span>
        </div>
      </footer>
    </div>
  );
}
