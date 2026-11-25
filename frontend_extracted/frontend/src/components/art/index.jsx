// ─────────────────────────────────────────────────────────────────────────────
// Background art, in the style of ui_demo/: light-grey line icons down both
// sides of a page (with mustard fills and red plus marks) and a themed band
// along the bottom. Every page gets art that matches what the page is about.
// All decorative (aria-hidden), drawn behind the content.
//
//   <PageDecor kind="script" />    kinds: see DECOR at the bottom
// ─────────────────────────────────────────────────────────────────────────────

const A = '#F3A641'                     // mustard
const P = '#F3D8B0'                     // pale mustard
const R = '#D92B3A'                     // red
const G = 'currentColor'               // line grey (class "art")
const BG = '#F1ECE4'                    // page colour, for cut-outs
const DARK = '#1E1E1E'
const FRAME = '#2E2E2E'
const TAUPE = '#8A8178'
const WARM = '#B86B0C'                  // darker mustard line
const GREY = '#D0CAC1'

const line = (w = 5) => ({ fill: 'none', stroke: G, strokeWidth: w, strokeLinecap: 'round', strokeLinejoin: 'round' })
const stroke = (c, w = 6) => ({ fill: 'none', stroke: c, strokeWidth: w, strokeLinecap: 'round', strokeLinejoin: 'round' })
const star = (cx, cy, r) => `M${cx} ${cy - r} L${cx + r * 0.22} ${cy - r * 0.22} L${cx + r} ${cy} L${cx + r * 0.22} ${cy + r * 0.22} L${cx} ${cy + r} L${cx - r * 0.22} ${cy + r * 0.22} L${cx - r} ${cy} L${cx - r * 0.22} ${cy - r * 0.22}Z`

const Svg = ({ vb = '0 0 100 100', children, ...p }) => (
  <svg viewBox={vb} aria-hidden="true" focusable="false" {...p}>{children}</svg>
)

// ── Icons ────────────────────────────────────────────────────────────────────
const I = {
  plus: (p) => <Svg {...p}><path d="M50 16 V84 M16 50 H84" {...stroke(R, 9)} /></Svg>,
  star: (p) => <Svg {...p}><path d={star(50, 50, 46)} fill={A} /></Svg>,
  sparkles: (p) => <Svg vb="0 0 120 120" {...p}><path d={star(44, 64, 40)} fill={A} /><path d={star(96, 22, 16)} fill={P} /><path d={star(100, 100, 12)} fill={A} /></Svg>,
  heart: (p) => <Svg {...p}><path d="M50 86 C20 64 8 48 16 30 C24 14 44 16 50 32 C56 16 76 14 84 30 C92 48 80 64 50 86Z" {...line(5)} /></Svg>,
  heartFill: (p) => <Svg {...p}><path d="M50 88 C18 64 6 48 14 28 C22 12 44 14 50 30 C56 14 78 12 86 28 C94 48 82 64 50 88Z" fill={A} /></Svg>,

  phonePlay: (p) => <Svg vb="0 0 100 130" {...p}><rect x="12" y="6" width="76" height="118" rx="12" {...line()} /><path d="M38 44 L70 65 L38 86Z" fill={A} /></Svg>,
  phoneButton: (p) => (
    <Svg vb="0 0 100 150" {...p}>
      <rect x="8" y="6" width="84" height="138" rx="14" {...line()} />
      <circle cx="50" cy="58" r="22" fill={A} /><path d="M44 47 L61 58 L44 69Z" fill={DARK} />
      <path d="M30 116 H70" {...line()} />
    </Svg>
  ),
  phoneProgress: (p) => (
    <Svg vb="0 0 100 170" {...p}>
      <rect x="8" y="8" width="84" height="154" rx="14" {...line()} />
      <path d="M40 62 L70 82 L40 102Z" fill={P} /><path d="M24 136 H58" {...stroke(A, 7)} /><path d="M58 136 H76" {...line()} />
    </Svg>
  ),
  bars: (p) => (
    <Svg vb="0 0 120 112" {...p}>
      <rect x="12" y="62" width="18" height="40" rx="2" fill={A} /><rect x="40" y="40" width="18" height="62" rx="2" fill={A} />
      <rect x="68" y="8" width="18" height="94" rx="2" fill={A} /><path d="M4 106 H116" {...line(5)} />
    </Svg>
  ),
  clapper: (p) => (
    <Svg vb="0 0 120 112" {...p}>
      <rect x="8" y="44" width="104" height="60" rx="8" {...line()} />
      <path d="M8 36 L110 26 L108 6 L6 16Z" {...line()} />
      <path d="M26 34 L34 12 M52 31 L60 9 M78 29 L86 7" {...stroke(A, 8)} />
    </Svg>
  ),
  clapperPlain: (p) => (
    <Svg vb="0 0 120 112" {...p}>
      <rect x="8" y="40" width="104" height="64" rx="8" {...line()} />
      <path d="M8 40 L18 10 H110 L112 40" {...line()} />
      <path d="M30 40 L40 12 M58 40 L68 12 M86 40 L96 12" {...stroke(A, 8)} />
      <path d="M26 66 H94 M26 84 H70" {...line(5)} />
    </Svg>
  ),
  avatar: (p) => (
    <Svg {...p}>
      <circle cx="50" cy="50" r="45" {...line()} /><circle cx="50" cy="38" r="13" fill={A} />
      <path d="M24 82 C28 60 72 60 76 82" {...line()} />
    </Svg>
  ),
  doc: (p) => (
    <Svg vb="0 0 100 120" {...p}>
      <rect x="10" y="6" width="80" height="108" rx="8" {...line()} />
      <path d="M26 34 H74 M26 52 H74 M26 70 H74 M26 88 H58" {...line(5)} />
    </Svg>
  ),
  docMark: (p) => (
    <Svg vb="0 0 100 120" {...p}>
      <rect x="10" y="6" width="80" height="108" rx="8" {...line()} />
      <path d="M26 32 H74" {...line(5)} /><rect x="18" y="45" width="64" height="15" rx="7.5" fill={A} />
      <path d="M26 52 H70" {...stroke(WARM, 5)} /><path d="M26 74 H74 M26 92 H58" {...line(5)} />
    </Svg>
  ),
  quote: (p) => (
    <Svg vb="0 0 124 92" {...p}>
      <path d="M8 86 V52 C8 26 20 10 46 6 V24 C32 28 28 36 28 48 H46 V86Z" fill={A} />
      <path d="M70 86 V52 C70 26 82 10 108 6 V24 C94 28 90 36 90 48 H108 V86Z" fill={A} />
    </Svg>
  ),
  bubble: (p) => (
    <Svg vb="0 0 124 104" {...p}>
      <path d="M8 8 H116 V72 H46 L28 96 V72 H8Z" {...line()} /><path d="M26 30 H98 M26 50 H70" {...line(5)} />
    </Svg>
  ),
  bubbleDots: (p) => (
    <Svg vb="0 0 124 104" {...p}>
      <path d="M8 8 H116 V72 H46 L28 96 V72 H8Z" {...line()} />
      <circle cx="38" cy="40" r="7" fill={A} /><circle cx="62" cy="40" r="7" fill={A} /><circle cx="86" cy="40" r="7" fill={A} />
    </Svg>
  ),
  squiggle: (p) => <Svg vb="0 0 140 40" {...p}><path d="M6 26 C24 4 42 4 52 22 S80 40 94 20 S122 4 134 22" {...stroke(A, 6)} /></Svg>,
  pencil: (p) => (
    <Svg vb="0 0 60 150" {...p}>
      <rect x="16" y="4" width="28" height="14" rx="3" fill={GREY} />
      <rect x="16" y="18" width="28" height="92" fill={A} />
      <path d="M16 110 H44 L30 140Z" {...line(4)} />
    </Svg>
  ),
  cursor: (p) => <Svg vb="0 0 60 120" {...p}><path d="M12 8 H48 M30 8 V112 M12 112 H48" {...stroke(A, 7)} /></Svg>,
  storyboard: (p) => (
    <Svg vb="0 0 90 240" {...p}>
      <rect x="6" y="6" width="78" height="228" rx="10" {...line()} />
      <rect x="20" y="22" width="50" height="52" {...line(4)} /><rect x="20" y="94" width="50" height="52" fill={A} />
      <rect x="20" y="166" width="50" height="52" {...line(4)} />
    </Svg>
  ),
  stopwatch: (p) => (
    <Svg vb="0 0 100 112" {...p}>
      <circle cx="50" cy="64" r="40" {...line()} /><path d="M50 8 V22 M38 8 H62" {...line()} />
      <path d="M50 40 V64 L66 76" {...stroke(A, 8)} />
    </Svg>
  ),
  filmCamera: (p) => (
    <Svg vb="0 0 140 170" {...p}>
      <circle cx="38" cy="28" r="22" fill={A} /><circle cx="38" cy="28" r="7" fill={BG} />
      <circle cx="88" cy="28" r="22" fill={P} /><circle cx="88" cy="28" r="7" fill={BG} />
      <rect x="12" y="56" width="92" height="60" rx="6" {...line()} />
      <path d="M104 74 L132 58 V114 L104 98" {...line()} /><path d="M40 116 L28 162 M76 116 L88 162" {...line()} />
    </Svg>
  ),
  flow: (p) => (
    <Svg vb="0 0 124 172" {...p}>
      <rect x="8" y="6" width="108" height="60" rx="6" {...line()} />
      <path d="M22 48 L42 28 L60 44 L78 26 L100 42" {...stroke(A, 6)} />
      <path d="M62 66 V98 M50 86 L62 98 L74 86" {...line()} />
      <rect x="8" y="104" width="108" height="60" rx="6" {...line()} />
    </Svg>
  ),
  ruler: (p) => <Svg vb="0 0 140 50" {...p}><path d="M6 25 H134 M6 8 V42 M48 14 V36 M90 14 V36 M134 8 V42" {...stroke(A, 6)} /></Svg>,
  imageCard: (p) => (
    <Svg vb="0 0 140 120" {...p}>
      <rect x="8" y="8" width="124" height="104" rx="8" {...line()} />
      <path d="M18 98 L54 58 L76 80 L96 64 L124 98Z" fill={P} /><circle cx="98" cy="36" r="12" fill={A} />
    </Svg>
  ),
  polaroid: (p) => <Svg vb="0 0 120 140" {...p}><rect x="8" y="8" width="104" height="124" rx="8" {...line()} /><rect x="22" y="22" width="76" height="76" fill={P} transform="rotate(3 60 60)" /></Svg>,
  imageOutline: (p) => (
    <Svg vb="0 0 140 112" {...p}>
      <rect x="8" y="8" width="124" height="96" rx="8" {...line()} /><path d="M20 90 L52 58 L74 80 L92 62 L120 92" {...line()} />
    </Svg>
  ),
  stack: (p) => <Svg vb="0 0 124 124" {...p}><rect x="36" y="8" width="80" height="80" rx="8" fill={P} /><rect x="8" y="36" width="80" height="80" rx="8" {...line()} /></Svg>,
  arrowUp: (p) => <Svg vb="0 0 100 140" {...p}><path d="M50 112 V20 M22 48 L50 20 L78 48" {...stroke(A, 7)} /><path d="M12 132 H88" {...line()} /></Svg>,
  photoCamera: (p) => (
    <Svg vb="0 0 140 120" {...p}>
      <rect x="8" y="28" width="124" height="86" rx="12" {...line()} /><path d="M44 28 L52 10 H88 L96 28" {...line()} />
      <circle cx="70" cy="70" r="24" fill={A} /><circle cx="70" cy="70" r="10" fill={BG} /><path d="M112 46 H122" {...line()} />
    </Svg>
  ),
  codeFile: (p) => (
    <Svg vb="0 0 120 170" {...p}>
      <path d="M8 8 H80 L112 40 V162 H8Z" {...line()} /><path d="M80 8 V40 H112" {...line()} />
      <path d="M46 74 L26 96 L46 118 M74 74 L94 96 L74 118" {...stroke(A, 7)} />
    </Svg>
  ),
  scissors: (p) => (
    <Svg vb="0 0 140 120" {...p}>
      <circle cx="26" cy="30" r="17" fill={A} /><circle cx="26" cy="90" r="17" fill={P} />
      <path d="M42 38 L132 92 M42 82 L132 28" {...line(5)} />
    </Svg>
  ),
  sliders: (p) => (
    <Svg vb="0 0 140 170" {...p}>
      <path d="M6 40 H134 M6 86 H134 M6 132 H134" {...line(5)} />
      <rect x="20" y="30" width="50" height="20" rx="4" fill={A} /><rect x="64" y="76" width="44" height="20" rx="4" fill={P} />
      <rect x="12" y="122" width="38" height="20" rx="4" fill={A} /><path d="M98 6 V164" {...stroke(R, 4)} />
    </Svg>
  ),
  monitor: (p) => (
    <Svg vb="0 0 160 142" {...p}>
      <rect x="8" y="8" width="144" height="96" rx="10" {...line()} /><path d="M66 30 L104 56 L66 82Z" fill={A} />
      <path d="M80 104 V124 M50 132 H110" {...line()} />
    </Svg>
  ),
  download: (p) => <Svg vb="0 0 120 140" {...p}><path d="M60 10 V94 M28 64 L60 96 L92 64" {...stroke(A, 8)} /><path d="M8 128 H112" {...line()} /></Svg>,
  calendar: (p) => (
    <Svg vb="0 0 140 140" {...p}>
      <rect x="8" y="24" width="124" height="108" rx="12" {...line()} /><path d="M8 52 H132 M40 8 V34 M100 8 V34" {...line()} />
      <path d="M24 80 H42 M62 80 H80 M100 80 H118 M24 106 H42 M100 106 H118" {...line(5)} />
      <rect x="56" y="96" width="30" height="20" rx="4" fill={A} />
    </Svg>
  ),
  clock: (p) => <Svg vb="0 0 110 110" {...p}><circle cx="55" cy="55" r="48" {...line()} /><path d="M55 24 V58 L76 72" {...stroke(A, 8)} /></Svg>,
  plane: (p) => (
    <Svg vb="0 0 160 160" {...p}>
      <path d="M6 82 L154 8 L98 152 L74 96Z" fill={A} /><path d="M154 8 L74 96" {...stroke(WARM, 3)} />
    </Svg>
  ),
  hash: (p) => <Svg vb="0 0 120 120" {...p}><path d="M46 8 L32 112 M90 8 L76 112 M12 40 H112 M6 80 H106" {...line(6)} /></Svg>,
  bulb: (p) => (
    <Svg vb="0 0 100 140" {...p}>
      <circle cx="50" cy="48" r="44" fill={P} />
      <path d="M32 76 C14 62 16 22 50 20 C84 22 86 62 68 76 V92 H32Z" {...line()} />
      <path d="M36 106 H64 M40 120 H60" {...line()} /><path d="M40 58 L50 70 L60 58" {...stroke(A, 6)} />
    </Svg>
  ),
  magnifier: (p) => <Svg vb="0 0 120 120" {...p}><circle cx="48" cy="48" r="34" {...line(6)} /><path d="M74 74 L110 110" {...stroke(A, 11)} /></Svg>,
  trend: (p) => (
    <Svg vb="0 0 140 112" {...p}>
      <path d="M8 8 V104 H132" {...line()} /><path d="M22 86 L52 58 L78 70 L118 26" {...stroke(A, 7)} />
      <path d="M96 24 H120 V48" {...stroke(A, 7)} />
    </Svg>
  ),
  target: (p) => (
    <Svg vb="0 0 120 120" {...p}>
      <circle cx="60" cy="60" r="52" {...line()} /><circle cx="60" cy="60" r="33" {...line()} /><circle cx="60" cy="60" r="15" fill={A} />
    </Svg>
  ),
  sticky: (p) => (
    <Svg vb="0 0 120 120" {...p}>
      <path d="M8 8 H112 V84 L84 112 H8Z" fill={P} /><path d="M84 112 V84 H112" {...line()} />
      <path d="M24 36 H92 M24 58 H74" {...line(5)} />
    </Svg>
  ),
  mic: (p) => (
    <Svg vb="0 0 100 150" {...p}>
      <rect x="30" y="8" width="40" height="70" rx="20" fill={A} />
      <path d="M16 62 C16 102 84 102 84 62 M50 100 V130 M30 138 H70" {...line()} />
    </Svg>
  ),
  wave: (p) => (
    <Svg vb="0 0 140 80" {...p}>
      {[20, 50, 34, 64, 28, 46, 18].map((h, i) => <path key={i} d={`M${12 + i * 19} ${40 - h / 2} V${40 + h / 2}`} {...stroke(A, 8)} />)}
    </Svg>
  ),
  folder: (p) => <Svg vb="0 0 140 120" {...p}><path d="M8 20 H52 L64 34 H132 V108 H8Z" {...line()} /><rect x="10" y="22" width="40" height="12" rx="3" fill={A} /></Svg>,
  bookmark: (p) => <Svg vb="0 0 80 120" {...p}><path d="M10 6 H70 V112 L40 88 L10 112Z" fill={A} /></Svg>,
  gear: (p) => (
    <Svg vb="0 0 120 120" {...p}>
      {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => {
        const r = (a * Math.PI) / 180
        return <path key={a} d={`M${60 + Math.cos(r) * 34} ${60 + Math.sin(r) * 34} L${60 + Math.cos(r) * 50} ${60 + Math.sin(r) * 50}`} {...line(11)} />
      })}
      <circle cx="60" cy="60" r="34" {...line(6)} /><circle cx="60" cy="60" r="13" fill={A} />
    </Svg>
  ),
  toggle: (p) => <Svg vb="0 0 140 70" {...p}><rect x="6" y="6" width="128" height="58" rx="29" {...line()} /><circle cx="100" cy="35" r="20" fill={A} /></Svg>,
  key: (p) => (
    <Svg vb="0 0 150 80" {...p}>
      <circle cx="34" cy="40" r="25" {...line()} /><circle cx="34" cy="40" r="9" fill={A} />
      <path d="M59 40 H140 M116 40 V60 M134 40 V56" {...stroke(A, 8)} />
    </Svg>
  ),
  lock: (p) => (
    <Svg vb="0 0 110 140" {...p}>
      <path d="M30 60 V40 C30 12 80 12 80 40 V60" {...line(6)} /><rect x="10" y="60" width="90" height="72" rx="12" {...line()} />
      <circle cx="55" cy="92" r="10" fill={A} /><path d="M55 100 V114" {...stroke(A, 7)} />
    </Svg>
  ),
  creditCard: (p) => (
    <Svg vb="0 0 160 112" {...p}>
      <rect x="8" y="8" width="144" height="96" rx="12" {...line()} /><rect x="9" y="30" width="142" height="18" fill={A} />
      <rect x="24" y="70" width="40" height="14" rx="4" fill={P} />
    </Svg>
  ),
  coins: (p) => (
    <Svg vb="0 0 120 130" {...p}>
      {[0, 1, 2, 3, 4].map((i) => <ellipse key={i} cx="52" cy={112 - i * 17} rx="40" ry="12" fill={i % 2 ? P : A} stroke={BG} strokeWidth="3" />)}
      <ellipse cx="52" cy="40" rx="40" ry="12" {...line(4)} />
    </Svg>
  ),
  receipt: (p) => (
    <Svg vb="0 0 100 140" {...p}>
      <path d="M10 8 H90 V130 L76 120 L62 130 L50 120 L38 130 L24 120 L10 130Z" {...line()} />
      <path d="M26 34 H74 M26 52 H62 M26 70 H74" {...line(5)} /><path d="M50 98 H74" {...stroke(A, 7)} />
    </Svg>
  ),
  tag: (p) => <Svg vb="0 0 140 140" {...p}><path d="M70 8 H130 V68 L64 134 L6 76Z" fill={A} /><circle cx="106" cy="32" r="9" fill={BG} /></Svg>,
  envelope: (p) => (
    <Svg vb="0 0 150 112" {...p}>
      <rect x="8" y="8" width="134" height="94" rx="10" {...line()} /><path d="M8 16 L75 62 L142 16" {...line()} />
      <circle cx="118" cy="84" r="15" fill={A} />
    </Svg>
  ),
  shield: (p) => (
    <Svg vb="0 0 120 140" {...p}>
      <path d="M60 8 L108 26 V64 C108 100 84 122 60 132 C36 122 12 100 12 64 V26Z" {...line()} />
      <path d="M36 70 L54 88 L86 52" {...stroke(A, 9)} />
    </Svg>
  ),
  reel: (p) => (
    <Svg vb="0 0 120 120" {...p}>
      <circle cx="60" cy="60" r="52" fill={A} />
      {[0, 72, 144, 216, 288].map((a) => {
        const r = ((a - 90) * Math.PI) / 180
        return <circle key={a} cx={60 + Math.cos(r) * 28} cy={60 + Math.sin(r) * 28} r="12" fill={BG} />
      })}
      <circle cx="60" cy="60" r="7" fill={BG} />
    </Svg>
  ),
  layers: (p) => (
    <Svg vb="0 0 140 130" {...p}>
      <path d="M70 86 L132 104 L70 122 L8 104Z" fill={P} />
      <path d="M8 68 L70 86 L132 68" {...stroke(A, 7)} />
      <path d="M70 8 L132 28 L70 48 L8 28Z" {...line()} />
    </Svg>
  ),
  chip: (p) => (
    <Svg vb="0 0 130 130" {...p}>
      {[42, 65, 88].map((i) => <path key={i} d={`M${i} 8 V26 M${i} 104 V122 M8 ${i} H26 M104 ${i} H122`} {...line(5)} />)}
      <rect x="26" y="26" width="78" height="78" rx="10" {...line()} /><rect x="46" y="46" width="38" height="38" rx="4" fill={A} />
    </Svg>
  ),
  reelGrid: (p) => (
    <Svg vb="0 0 132 120" {...p}>
      {[0, 1, 2].flatMap((c) => [0, 1].map((r) => {
        const fill = c === 1 && r === 0 ? A : c === 2 && r === 1 ? P : null
        return <rect key={`${c}${r}`} x={6 + c * 42} y={6 + r * 58} width="36" height="50" rx="5" {...(fill ? { fill } : line(4))} />
      }))}
      <path d="M59 22 L71 31 L59 40Z" fill={BG} />
    </Svg>
  ),
}

// ── Bottom bands (1440 × 200, cropped at the sides on small screens) ─────────
const Band = ({ children, className }) => (
  <svg viewBox="0 0 1440 200" preserveAspectRatio="xMidYMax slice" className={className} aria-hidden="true" focusable="false">{children}</svg>
)

const BANDS = {
  chart: () => (
    <Band className="art h-full w-full">
      <path d="M0 200 L0 172 L160 142 L330 160 L510 112 L690 128 L890 80 L1070 94 L1250 42 L1440 16 L1440 200Z" fill={P} opacity=".75" />
      <path d="M0 172 L160 142 L330 160 L510 112 L690 128 L890 80 L1070 94 L1250 42 L1400 18" {...stroke(A, 6)} />
      {[[160, 142], [510, 112], [890, 80], [1250, 42]].map(([x, y]) => <circle key={x} cx={x} cy={y} r="11" fill={A} />)}
      <path d="M1360 10 L1406 16 L1388 58" {...stroke(A, 6)} />
    </Band>
  ),
  wave: () => (
    <Band className="art h-full w-full">
      <rect x="24" y="156" width="1392" height="28" rx="14" fill={P} opacity=".75" />
      <path d="M0 150 C120 100 230 66 390 84 S610 196 770 166 S1010 30 1150 62 S1370 158 1440 128" {...stroke(A, 6)} />
    </Band>
  ),
  film: () => (
    <Band className="art h-full w-full">
      <g transform="rotate(-5 720 150)">
        <rect x="-120" y="104" width="1680" height="96" fill={A} />
        {Array.from({ length: 34 }, (_, i) => (
          <g key={i}><rect x={-100 + i * 50} y="116" width="26" height="11" rx="2" fill={BG} /><rect x={-100 + i * 50} y="176" width="26" height="11" rx="2" fill={BG} /></g>
        ))}
        <path d="M-120 152 H1560" stroke={BG} strokeWidth="2" opacity=".6" />
      </g>
    </Band>
  ),
  mountains: () => (
    <Band className="art h-full w-full">
      <path d="M0 200 L0 170 L230 60 L420 148 L650 18 L900 160 L900 200Z" fill={P} opacity=".8" />
      <path d="M0 170 L230 60 L420 148 L650 18 L890 154" {...line(4)} />
      <path d="M540 200 L1050 86 L1440 190 L1440 200Z" fill="#F3A641" fillOpacity=".45" />
      <path d="M760 200 L1440 120 L1440 200Z" fill={P} opacity=".9" />
      <circle cx="1180" cy="128" r="74" fill={A} />
    </Band>
  ),
  waveform: () => {
    const h = [70, 110, 150, 84, 196, 120, 64, 150, 90, 56, 44, 104, 140, 92, 196, 116, 76, 150, 104, 60, 112, 150, 84, 196, 120, 64, 150, 90, 120, 60]
    return (
      <Band className="art h-full w-full">
        {h.map((v, i) => <rect key={i} x={20 + i * 48} y={200 - v} width="15" height={v + 10} rx="7.5" fill={i < 19 ? A : G} />)}
        <path d="M934 0 V200" {...stroke(R, 4)} />
      </Band>
    )
  },
  dotted: () => (
    <Band className="art h-full w-full">
      <path d="M0 186 C200 150 400 128 620 150 S900 194 1080 128 S1300 70 1440 104" fill="none" stroke={A} strokeWidth="8" strokeLinecap="round" strokeDasharray="0 24" />
      <g transform="translate(250 110) scale(.6)"><path d="M50 88 C18 64 6 48 14 28 C22 12 44 14 50 30 C56 14 78 12 86 28 C94 48 82 64 50 88Z" fill={A} /></g>
      <g transform="translate(990 136) scale(.5)"><path d="M50 88 C18 64 6 48 14 28 C22 12 44 14 50 30 C56 14 78 12 86 28 C94 48 82 64 50 88Z" fill={P} /></g>
      <g transform="translate(1040 44) scale(.55)"><path d="M50 88 C18 64 6 48 14 28 C22 12 44 14 50 30 C56 14 78 12 86 28 C94 48 82 64 50 88Z" fill={A} /></g>
      <g transform="translate(1310 20) scale(.75)"><path d="M6 82 L154 8 L98 152 L74 96Z" fill={A} /></g>
    </Band>
  ),
  ideas: () => {
    const nodes = [[60, 150, 'p'], [230, 96, 'a'], [400, 160, 'o'], [570, 80, 'p'], [760, 150, 'a'], [940, 90, 'o'], [1120, 156, 'p']]
    return (
      <Band className="art h-full w-full">
        <path d={`M${nodes.map(([x, y]) => `${x} ${y}`).join(' L')} L1290 110`} fill="none" stroke={A} strokeWidth="5" strokeDasharray="16 14" strokeLinecap="round" />
        {nodes.map(([x, y, t]) => (t === 'a' ? <circle key={x} cx={x} cy={y} r="15" fill={A} />
          : t === 'p' ? <circle key={x} cx={x} cy={y} r="22" fill={P} /> : <circle key={x} cx={x} cy={y} r="13" {...line(5)} />))}
        <g transform="translate(1260 30) scale(1.15)">
          <circle cx="50" cy="48" r="44" fill={P} />
          <path d="M32 76 C14 62 16 22 50 20 C84 22 86 62 68 76 V92 H32Z" {...line()} />
          <path d="M36 106 H64 M40 120 H60" {...line()} /><path d="M40 58 L50 70 L60 58" {...stroke(A, 6)} />
        </g>
      </Band>
    )
  },
  chips: () => {
    const chips = [[40, 128, 170, 'p'], [250, 150, 200, 'a'], [490, 118, 140, 'o'], [670, 152, 220, 'p'], [930, 124, 160, 'a'], [1130, 150, 140, 'o'], [1300, 120, 170, 'p']]
    return (
      <Band className="art h-full w-full">
        {chips.map(([x, y, w, t]) => (
          <g key={x}>
            <rect x={x} y={y} width={w} height="46" rx="23" {...(t === 'a' ? { fill: A } : t === 'p' ? { fill: P } : line(5))} />
            <path d={`M${x + 24} ${y + 23} H${x + w * 0.6}`} {...stroke(t === 'o' ? G : BG, 6)} />
          </g>
        ))}
      </Band>
    )
  },
  reels: () => (
    <Band className="art h-full w-full">
      {Array.from({ length: 12 }, (_, i) => {
        const t = ['p', 'o', 'a', 'o', 'p', 'a'][i % 6]
        const x = 30 + i * 120
        return (
          <g key={i} transform={`rotate(${i % 2 ? 5 : -5} ${x + 40} 150)`}>
            <rect x={x} y={78 + (i % 3) * 14} width="80" height="140" rx="12" {...(t === 'a' ? { fill: A } : t === 'p' ? { fill: P } : line(5))} />
            {t === 'a' && <path d={`M${x + 32} ${130 + (i % 3) * 14} L${x + 54} ${146 + (i % 3) * 14} L${x + 32} ${162 + (i % 3) * 14}Z`} fill={BG} />}
          </g>
        )
      })}
    </Band>
  ),
  render: () => (
    <Band className="art h-full w-full">
      <rect x="0" y="106" width="1440" height="94" fill={DARK} />
      {Array.from({ length: 37 }, (_, i) => (
        <g key={i}><rect x={8 + i * 40} y="114" width="22" height="8" rx="2" fill={BG} /><rect x={8 + i * 40} y="186" width="22" height="8" rx="2" fill={BG} /></g>
      ))}
      {Array.from({ length: 12 }, (_, i) => (
        <rect key={i} x={14 + i * 120} y="132" width="104" height="46" rx="5" fill={i < 7 ? A : i === 7 ? P : FRAME} />
      ))}
    </Band>
  ),
  tracks: () => {
    const segs = [[A, 180], [DARK, 140], [R, 240], [TAUPE, 200], [null, 140]]
    let x = 20
    const row = []
    for (let k = 0; k < 2; k++) for (const [c, w] of segs) { row.push([x, w, c]); x += w + 10 }
    return (
      <Band className="art h-full w-full">
        <path d={Array.from({ length: 49 }, (_, i) => `M${20 + i * 30} 56 V${i % 5 ? 66 : 74}`).join(' ')} {...line(3)} />
        {Array.from({ length: 11 }, (_, i) => <rect key={i} x={30 + i * 130} y="86" width="96" height="20" rx="4" {...line(4)} />)}
        {row.map(([rx, w, c]) => <rect key={rx} x={rx} y="120" width={w} height="34" rx="5" {...(c ? { fill: c } : line(4))} />)}
        {Array.from({ length: 70 }, (_, i) => {
          const h = 6 + ((i * 37) % 22)
          return <rect key={i} x={20 + i * 20.5} y={182 - h / 2} width="8" height={h} rx="4" fill={P} />
        })}
        <path d="M700 40 V200" {...stroke(R, 4)} /><path d="M690 36 L700 26 L710 36 L700 46Z" fill={R} />
      </Band>
    )
  },
  shelf: () => {
    let x = 30
    const items = []
    const widths = [46, 64, 40, 70, 52, 44, 66, 58, 40, 72, 50, 62, 44, 68, 54, 46, 60, 50, 70, 44, 58, 48]
    widths.forEach((w, i) => { items.push([x, w, 70 + ((i * 53) % 90), ['a', 'o', 'p', 'o', 'a', 'p', 'o'][i % 7]]); x += w + 12 })
    return (
      <Band className="art h-full w-full">
        {items.map(([ix, w, h, t]) => <rect key={ix} x={ix} y={192 - h} width={w} height={h} rx="6" {...(t === 'a' ? { fill: A } : t === 'p' ? { fill: P } : line(5))} />)}
        <path d="M0 194 H1440" {...line(6)} />
      </Band>
    )
  },
  rails: () => (
    <Band className="art h-full w-full">
      <path d="M0 96 H1440 M0 138 H1440 M0 180 H1440" {...line(6)} />
      {[[260, 96, A], [940, 96, P], [560, 138, A], [1240, 138, A], [120, 180, P], [800, 180, A]].map(([x, y, c]) => (
        <rect key={`${x}${y}`} x={x} y={y - 15} width="96" height="30" rx="8" fill={c} />
      ))}
    </Band>
  ),
  coins: () => (
    <Band className="art h-full w-full">
      {Array.from({ length: 10 }, (_, s) => {
        const x = 80 + s * 140
        const n = 2 + Math.round(s * 0.75)
        return Array.from({ length: n }, (_, i) => (
          <ellipse key={`${s}-${i}`} cx={x} cy={184 - i * 16} rx="44" ry="13" fill={(i + s) % 2 ? P : A} stroke={BG} strokeWidth="3" />
        ))
      })}
      <path d="M0 196 H1440" {...line(5)} />
    </Band>
  ),
}

// ── Page sets: [icon, top(px), width(px), rotate(deg), x offset(px)] ────────
const DECOR = {
  dashboard: {
    left: [['phonePlay', 40, 104, -10], ['plus', 270, 44, 0, 92], ['bars', 360, 112], ['clapper', 600, 112, -4]],
    right: [['phoneButton', 30, 92], ['plus', 262, 44, 0, 104], ['avatar', 340, 100], ['heart', 480, 70, 0, 20], ['star', 640, 86, 0, 20]],
    band: 'chart',
  },
  script: {
    left: [['docMark', 30, 104, -8], ['plus', 250, 44, 0, 96], ['quote', 330, 92], ['bubble', 640, 112], ['squiggle', 830, 112]],
    right: [['pencil', 20, 56, 38, 30], ['plus', 260, 44, 0, 104], ['doc', 330, 100, 8], ['cursor', 600, 40, 0, 30]],
    band: 'wave',
  },
  production: {
    left: [['clapperPlain', 40, 108, -4], ['plus', 200, 44, 0, 92], ['storyboard', 290, 68, 0, 20], ['stopwatch', 560, 82, 0, 14]],
    right: [['filmCamera', 30, 104], ['plus', 230, 44, 0, 104], ['flow', 320, 96], ['ruler', 520, 106]],
    band: 'film',
  },
  photos: {
    left: [['imageCard', 40, 118, -6], ['plus', 260, 44, 0, 94], ['polaroid', 340, 100, -4], ['arrowUp', 620, 76, 0, 30]],
    right: [['photoCamera', 50, 118], ['plus', 270, 44, 0, 100], ['imageOutline', 360, 112, 6], ['stack', 600, 96], ['star', 760, 60, 0, 30]],
    band: 'mountains',
  },
  output: {
    left: [['codeFile', 30, 100, 0], ['plus', 290, 44, 0, 94], ['scissors', 360, 104], ['sliders', 560, 108]],
    right: [['monitor', 50, 118], ['plus', 260, 44, 0, 100], ['download', 330, 84, 0, 20], ['phoneProgress', 560, 76, 0, 22], ['star', 760, 60, 0, 30]],
    band: 'waveform',
  },
  publish: {
    left: [['calendar', 40, 108], ['plus', 270, 44, 0, 96], ['heartFill', 380, 84, 0, 16], ['clock', 600, 90, 0, 12]],
    right: [['plane', 30, 120], ['hash', 330, 88, 0, 20], ['plus', 480, 44, 0, 100], ['bubbleDots', 560, 108]],
    band: 'dotted',
  },
  ideation: {
    left: [['bulb', 30, 92, -6, 6], ['plus', 260, 44, 0, 94], ['magnifier', 340, 92, 0, 10], ['sticky', 560, 96, -6]],
    right: [['trend', 40, 112], ['plus', 260, 44, 0, 104], ['target', 340, 96, 0, 10], ['sparkles', 560, 92, 0, 10]],
    band: 'ideas',
  },
  topics: {
    left: [['target', 30, 100, 0, 6], ['plus', 240, 44, 0, 94], ['sticky', 320, 96, 6], ['hash', 560, 80, 0, 18]],
    right: [['magnifier', 40, 92, 0, 14], ['plus', 240, 44, 0, 104], ['trend', 330, 108], ['star', 560, 70, 0, 24]],
    band: 'chips',
  },
  onboarding: {
    left: [['reelGrid', 40, 110], ['plus', 250, 44, 0, 94], ['mic', 320, 68, 0, 24], ['wave', 580, 104]],
    right: [['avatar', 40, 100], ['plus', 240, 44, 0, 104], ['phonePlay', 320, 92, 8, 10], ['sparkles', 560, 92, 0, 10]],
    band: 'reels',
  },
  video: {
    left: [['reel', 40, 100, 0, 6], ['plus', 240, 44, 0, 94], ['phoneButton', 320, 84, -6, 14], ['sparkles', 580, 90, 0, 10]],
    right: [['chip', 40, 104], ['plus', 260, 44, 0, 104], ['clapper', 340, 108, 4], ['star', 560, 64, 0, 24]],
    band: 'render',
  },
  xml: {
    left: [['codeFile', 30, 96], ['plus', 270, 44, 0, 94], ['layers', 350, 108], ['scissors', 560, 100]],
    right: [['download', 40, 84, 0, 20], ['plus', 230, 44, 0, 104], ['sliders', 310, 108], ['star', 560, 64, 0, 24]],
    band: 'tracks',
  },
  library: {
    left: [['folder', 40, 112], ['plus', 240, 44, 0, 94], ['phonePlay', 320, 88, -8, 12], ['reelGrid', 540, 104]],
    right: [['bookmark', 40, 64, 0, 24], ['plus', 220, 44, 0, 104], ['clapper', 300, 108, 4], ['heart', 500, 72, 0, 20]],
    band: 'shelf',
  },
  settings: {
    left: [['gear', 40, 100, 0, 6], ['plus', 240, 44, 0, 94], ['toggle', 330, 104], ['key', 520, 110, -10]],
    right: [['sliders', 40, 104], ['plus', 260, 44, 0, 104], ['avatar', 340, 92, 0, 6], ['lock', 520, 80, 0, 16]],
    band: 'rails',
  },
  billing: {
    left: [['creditCard', 40, 116, -6], ['plus', 240, 44, 0, 94], ['coins', 320, 100], ['receipt', 540, 80, -6, 14]],
    right: [['tag', 40, 100, 0, 6], ['plus', 260, 44, 0, 104], ['shield', 340, 88, 0, 10], ['star', 560, 70, 0, 24]],
    band: 'coins',
  },
  auth: {
    left: [['lock', 40, 84, 0, 12], ['plus', 260, 44, 0, 94], ['avatar', 340, 92, 0, 6], ['key', 520, 110, -10]],
    right: [['envelope', 40, 112], ['plus', 240, 44, 0, 104], ['shield', 320, 88, 0, 12], ['star', 520, 64, 0, 24]],
    band: 'film',
  },
  landing: {
    left: [['phonePlay', 60, 100, -10], ['plus', 300, 44, 0, 92], ['bars', 400, 108], ['clapper', 700, 108, -4], ['quote', 1100, 86], ['plus', 1400, 40, 0, 80], ['reelGrid', 1500, 104]],
    right: [['plane', 50, 116], ['plus', 300, 44, 0, 104], ['heartFill', 420, 80, 0, 18], ['star', 720, 76, 0, 24], ['bubbleDots', 1100, 104], ['plus', 1380, 40, 0, 100], ['sparkles', 1500, 88, 0, 12]],
    band: 'film',
  },
}
// older keys
DECOR.topic = DECOR.topics
DECOR.studio = DECOR.dashboard

function Side({ items, side }) {
  return (
    <div className={`pointer-events-none absolute top-0 ${side === 'left' ? 'left-[1.2vw]' : 'right-[1.2vw]'} hidden h-full w-[130px] [@media(min-width:1380px)]:block`}>
      {items.map(([name, top, width, rot = 0, x = 0], i) => {
        const Icon = I[name]
        return Icon ? (
          <Icon key={i} className="art absolute h-auto" style={{ top, [side]: x, width, transform: rot ? `rotate(${rot}deg)` : undefined }} />
        ) : null
      })}
    </div>
  )
}

/** The decoration for one page kind: side icons (wide screens) + bottom band. */
export function PageDecor({ kind }) {
  const set = DECOR[kind]
  if (!set) return null
  const B = BANDS[set.band]
  return (
    <div className="pointer-events-none absolute inset-0 -z-10 select-none" aria-hidden="true">
      <Side items={set.left} side="left" />
      <Side items={set.right} side="right" />
      {B && <div className="absolute inset-x-0 bottom-0 h-[150px] sm:h-[180px]"><B /></div>}
    </div>
  )
}

/** A single icon by name, for screens that place art themselves. */
export function ArtIcon({ name, className = '', style }) {
  const Icon = I[name]
  return Icon ? <Icon className={`art ${className}`} style={style} /> : null
}

/** A bottom band by name, e.g. for full-screen pages without <Page>. */
export function ArtBand({ name, className = '' }) {
  const B = BANDS[name]
  return B ? <div className={`pointer-events-none select-none ${className}`} aria-hidden="true"><B /></div> : null
}

export { DECOR }
