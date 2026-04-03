import React, { useState, useRef } from 'react';
import { motion, useInView, AnimatePresence } from 'framer-motion';
import {
  Terminal, Cpu, FileCode, GitBranch, Shield, Zap, CheckCircle2,
  ArrowRight, Code2, Database, Globe, Layers, Search,
  FlaskConical, Brain, ChevronDown, ExternalLink, Award,
} from 'lucide-react';
import './App.css';

const PIPELINE_MODULES = [
  { name: 'COBOL Parser', desc: 'Full AST with conditional logic trees', icon: FileCode, color: '#6366f1' },
  { name: 'Graph Builder', desc: 'Dependency graph across all programs', icon: GitBranch, color: '#8b5cf6' },
  { name: 'Copybook Dict', desc: 'Typed field catalog from .cpy files', icon: Database, color: '#a855f7' },
  { name: 'BMS Parser', desc: 'Screen layouts and field attributes', icon: Layers, color: '#c084fc' },
  { name: 'Skeleton Gen', desc: 'Python/Java/C# with typed fields', icon: Code2, color: '#38bdf8' },
  { name: 'Business Rules', desc: 'Evidence-anchored rule extraction', icon: Brain, color: '#2dd4bf' },
  { name: 'Repository Map', desc: 'CICS file ops to typed interfaces', icon: Database, color: '#34d399' },
  { name: 'API Contracts', desc: 'BMS screens to Pydantic + FastAPI', icon: Globe, color: '#4ade80' },
  { name: 'CobolDecimal', desc: 'Faithful PIC precision arithmetic', icon: Cpu, color: '#fbbf24' },
  { name: 'Diff Harness', desc: 'Field-by-field equivalence checking', icon: FlaskConical, color: '#f97316' },
  { name: 'Symbol Table', desc: 'Hierarchical qualified references', icon: Search, color: '#fb7185' },
  { name: 'CICS Stub', desc: 'Preprocessor for standalone execution', icon: Zap, color: '#f43f5e' },
];

const IQ_ITEMS = [
  { id: 'IQ-01', name: 'Conditional Logic', tests: 22 },
  { id: 'IQ-02', name: 'Copybook Wiring', tests: 12 },
  { id: 'IQ-03', name: 'Numeric Semantics', tests: 49 },
  { id: 'IQ-04', name: 'Business Rules', tests: 15 },
  { id: 'IQ-05', name: 'Behavioral Tests', tests: 10 },
  { id: 'IQ-06', name: 'Repository Mapping', tests: 14 },
  { id: 'IQ-07', name: 'API Contracts', tests: 15 },
  { id: 'IQ-08', name: 'Multi-Language', tests: 27 },
  { id: 'IQ-09', name: 'Diff Harness', tests: 15 },
  { id: 'IQ-10', name: 'Symbol Table', tests: 12 },
];

const CODEBASES = [
  {
    name: 'AWS CardDemo',
    desc: 'Credit card management \u2014 CICS online + batch processing',
    programs: 44, lines: '30K', type: 'CICS + Batch',
    reimpl: 'COSGN00C sign-on program',
    scenarios: [
      { name: 'Admin Login', input: 'ADMIN001 + PASS1234', expected: 'XCTL \u2192 COADM01C', match: true },
      { name: 'Regular Login', input: 'USER0001 + MYPASSWD', expected: 'XCTL \u2192 COMEN01C', match: true },
      { name: 'Wrong Password', input: 'ADMIN001 + WRONGPWD', expected: 'Error message, no transfer', match: true },
      { name: 'User Not Found', input: 'UNKNOWN1 + ANYTHING', expected: 'Error message, no transfer', match: true },
    ],
    fields_compared: 18, confidence: 100,
  },
  {
    name: 'Star Trek',
    desc: '1979 game \u2014 deep nesting, GO TO, random generation',
    programs: 1, lines: '1.6K', type: 'Interactive',
    reimpl: 'ctrek.cob \u2192 star_trek.py (1,615 lines)',
    scenarios: [
      { name: 'Title Screen', input: 'Any input', expected: '*STAR TREK* displayed', match: true },
      { name: 'Invalid Skill', input: 'Level 9', expected: 'INVALID SKILL LEVEL', match: true },
      { name: 'Skill Levels 1\u20134', input: 'All valid', expected: 'Accepted', match: true },
      { name: 'Klingon Counts', input: 'Skill 1/2/3/4', expected: '15 / 18 / 22 / 26', match: true },
      { name: 'Status Command', input: 'com 1', expected: 'Fuel + Shield display', match: true },
      { name: 'Terminate', input: 'com 6', expected: 'Game over + stranded', match: true },
    ],
    fields_compared: 12, confidence: 100,
  },
  {
    name: 'Taxe Fonci\u00e8re',
    desc: 'French property tax \u2014 EVALUATE ALSO, complex computation',
    programs: 6, lines: '3K', type: 'Subroutine',
    reimpl: 'EFITA3B8 \u2192 taxe_fonciere.py (669 lines)',
    scenarios: [
      { name: 'Valid Input (no rates)', input: 'ccobnb=2, dan=2018', expected: 'CR=24 RC=01', match: true },
      { name: 'Wrong Article Code', input: 'ccobnb=1', expected: 'CR=12 RC=01', match: true },
      { name: 'Wrong Year', input: 'dan=2019', expected: 'CR=12 RC=02', match: true },
      { name: 'Empty Input', input: 'All blank', expected: 'CR=12', match: true },
    ],
    fields_compared: 8, confidence: 100,
  },
];


function Section({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-100px" });
  return (
    <motion.section ref={ref} initial={{ opacity: 0, y: 60 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.8 }}
      className={`section ${className}`}>
      {children}
    </motion.section>
  );
}

function StatCard({ value, label, icon: Icon, delay = 0 }: any) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true });
  return (
    <motion.div ref={ref} className="stat-card"
      initial={{ opacity: 0, scale: 0.8 }}
      animate={isInView ? { opacity: 1, scale: 1 } : {}}
      transition={{ duration: 0.5, delay }}>
      <Icon size={32} className="stat-icon" />
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </motion.div>
  );
}

function ConfidenceRing({ value, label }: { value: number; label: string }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true });
  return (
    <div ref={ref} className="confidence-meter">
      <svg viewBox="0 0 120 120" className="confidence-svg">
        <circle cx="60" cy="60" r="50" fill="none" stroke="#1e293b" strokeWidth="10" />
        <motion.circle cx="60" cy="60" r="50" fill="none" stroke="#4ade80" strokeWidth="10"
          strokeLinecap="round" strokeDasharray={`${value * 3.14} 314`}
          initial={{ strokeDasharray: "0 314" }}
          animate={isInView ? { strokeDasharray: `${value * 3.14} 314` } : {}}
          transition={{ duration: 1.5, delay: 0.3 }} transform="rotate(-90 60 60)" />
        <text x="60" y="55" textAnchor="middle" fill="white" fontSize="22" fontWeight="bold">{value}%</text>
        <text x="60" y="73" textAnchor="middle" fill="#94a3b8" fontSize="10">confidence</text>
      </svg>
      <div className="confidence-label">{label}</div>
    </div>
  );
}

function CodeBlock({ code, lang = 'python' }: { code: string; lang?: string }) {
  return (
    <div className="code-block">
      <div className="code-header">
        <span className="code-dot red" /><span className="code-dot yellow" /><span className="code-dot green" />
        <span className="code-lang">{lang}</span>
      </div>
      <pre><code>{code}</code></pre>
    </div>
  );
}

function App() {
  const [activeTab, setActiveTab] = useState(0);

  return (
    <div className="app">
      {/* ── Hero ── */}
      <header className="hero">
        <motion.div initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1 }}>
          <div className="hero-badge">COBOL Intelligence Engine</div>
          <h1 className="hero-title"><span className="gradient-text">Masquerade</span></h1>
          <p className="hero-subtitle">
            Analyze. Reimplement. Verify. &mdash; End-to-end COBOL modernization
            with proven behavioral equivalence.
          </p>
          <div className="hero-stats">
            <div className="hero-stat"><strong>465</strong> programs</div>
            <div className="hero-stat-divider" />
            <div className="hero-stat"><strong>124K</strong> lines</div>
            <div className="hero-stat-divider" />
            <div className="hero-stat"><strong>392</strong> tests</div>
            <div className="hero-stat-divider" />
            <div className="hero-stat"><strong>100%</strong> match</div>
          </div>
        </motion.div>
        <motion.div className="scroll-indicator" animate={{ y: [0, 10, 0] }} transition={{ repeat: Infinity, duration: 2 }}>
          <ChevronDown size={32} />
        </motion.div>
      </header>

      {/* ── Stats ── */}
      <Section className="stats-section">
        <div className="stats-grid">
          <StatCard value="4" label="Codebases Tested" icon={Database} delay={0} />
          <StatCard value="12" label="Pipeline Modules" icon={Layers} delay={0.1} />
          <StatCard value="10/10" label="IQ Items Complete" icon={Award} delay={0.2} />
          <StatCard value="3" label="Target Languages" icon={Globe} delay={0.3} />
        </div>
      </Section>

      {/* ── Pipeline ── */}
      <Section>
        <h2 className="section-title">Pipeline Architecture</h2>
        <p className="section-desc">12 modules that transform raw COBOL into verified modern code</p>
        <div className="pipeline-grid">
          {PIPELINE_MODULES.map((mod, i) => (
            <motion.div key={i} className="pipeline-card"
              whileHover={{ scale: 1.05, y: -5 }}
              initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }} transition={{ delay: i * 0.05 }}>
              <mod.icon size={28} color={mod.color} />
              <h3>{mod.name}</h3>
              <p>{mod.desc}</p>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* ── IQ Checklist ── */}
      <Section>
        <h2 className="section-title">Implementation Quality</h2>
        <p className="section-desc">10 spec-driven, test-driven improvements &mdash; all complete</p>
        <div className="iq-grid">
          {IQ_ITEMS.map((item, i) => (
            <motion.div key={i} className="iq-card"
              initial={{ opacity: 0, scale: 0.9 }} whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }} transition={{ delay: i * 0.05 }}>
              <div className="iq-header">
                <CheckCircle2 size={20} color="#4ade80" />
                <span className="iq-id">{item.id}</span>
              </div>
              <div className="iq-name">{item.name}</div>
              <div className="iq-tests">{item.tests} tests</div>
            </motion.div>
          ))}
        </div>
      </Section>

      {/* ── THE PROOF ── */}
      <Section className="proof-section">
        <h2 className="section-title">The Proof</h2>
        <p className="section-desc">Same input &rarr; COBOL output vs Python output &rarr; field-by-field &rarr; 100% match</p>

        <div className="proof-tabs">
          {CODEBASES.map((cb, i) => (
            <button key={i} className={`proof-tab ${activeTab === i ? 'active' : ''}`}
              onClick={() => setActiveTab(i)}>
              {cb.name}
            </button>
          ))}
        </div>

        <AnimatePresence mode="wait">
          <motion.div key={activeTab} initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }} className="proof-content">

            <div className="proof-header">
              <div>
                <h3>{CODEBASES[activeTab].name}</h3>
                <p className="proof-desc">{CODEBASES[activeTab].desc}</p>
                <div className="proof-meta">
                  <span>{CODEBASES[activeTab].programs} programs</span>
                  <span>{CODEBASES[activeTab].lines} lines</span>
                  <span>{CODEBASES[activeTab].type}</span>
                </div>
              </div>
              <ConfidenceRing value={CODEBASES[activeTab].confidence}
                label={`${CODEBASES[activeTab].fields_compared} fields compared`} />
            </div>

            <div className="reimpl-badge">{CODEBASES[activeTab].reimpl}</div>

            <div className="scenario-table">
              <div className="scenario-header">
                <span>Scenario</span><span>Input</span><span>Expected Output</span><span></span>
              </div>
              {CODEBASES[activeTab].scenarios.map((s, i) => (
                <motion.div key={i} className="scenario-row"
                  initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.08 }}>
                  <span className="scenario-name">{s.name}</span>
                  <span className="scenario-input">{s.input}</span>
                  <span className="scenario-expected">{s.expected}</span>
                  <span><CheckCircle2 size={20} color="#4ade80" /></span>
                </motion.div>
              ))}
            </div>

            <div className="proof-flow">
              <div className="flow-step"><Terminal size={22} /><span>COBOL</span></div>
              <ArrowRight size={20} className="flow-arrow" />
              <div className="flow-step"><Cpu size={22} /><span>GnuCOBOL</span></div>
              <ArrowRight size={20} className="flow-arrow" />
              <div className="flow-step"><FlaskConical size={22} /><span>Compare</span></div>
              <ArrowRight size={20} className="flow-arrow" />
              <div className="flow-step match"><CheckCircle2 size={22} /><span>100%</span></div>
            </div>
          </motion.div>
        </AnimatePresence>
      </Section>

      {/* ── Code Samples ── */}
      <Section>
        <h2 className="section-title">What Gets Generated</h2>
        <div className="code-samples">
          <CodeBlock code={`@dataclass
class CdemoGeneralInfo:
    cdemo_user_id: str = field(
        default='',
        metadata={'pic': 'X(08)', 'max_length': 8}
    )
    CDEMO_USRTYP_ADMIN: ClassVar[str] = 'A'
    cdemo_user_type: str = field(
        default='',
        metadata={'pic': 'X(01)', 'max_length': 1}
    )`} lang="python &mdash; Typed Dataclass" />
          <CodeBlock code={`class WsUsrsecFileRepository:
    def find_by_id(
        self, ws_user_id: str
    ) -> Optional[SecUserData]:
        """CICS READ RIDFLD(WS-USER-ID)"""
        raise NotImplementedError`} lang="python &mdash; Repository" />
          <CodeBlock code={`class Cosgn0aRequest(BaseModel):
    userid: str = Field(
        ..., max_length=8,
        description='Primary input'
    )
    passwd: str = Field(
        ..., max_length=8,
        json_schema_extra={'writeOnly': True}
    )`} lang="python &mdash; API Contract" />
        </div>
      </Section>

      {/* ── Final ── */}
      <Section className="final-section">
        <motion.div className="final-content"
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }}>
          <div className="final-badge"><Shield size={20} /> Proven Behavioral Equivalence</div>
          <h2 className="final-title">
            Every reimplementation is <span className="gradient-text">verified</span> against
            the original COBOL &mdash; field by field, deterministically.
          </h2>
          <div className="final-stats">
            <div className="final-stat"><div className="final-stat-value">35</div><div className="final-stat-label">fields compared</div></div>
            <div className="final-stat"><div className="final-stat-value">13</div><div className="final-stat-label">test vectors</div></div>
            <div className="final-stat"><div className="final-stat-value">0</div><div className="final-stat-label">mismatches</div></div>
          </div>
          <a href="https://github.com/billybillymc/masquerade-cobol" className="github-button"
            target="_blank" rel="noreferrer">
            <ExternalLink size={18} /> View on GitHub
          </a>
        </motion.div>
      </Section>

      <footer className="footer">Masquerade COBOL Intelligence Engine &mdash; MIT License</footer>
    </div>
  );
}

export default App;
