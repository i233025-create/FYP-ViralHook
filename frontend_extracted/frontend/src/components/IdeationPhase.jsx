import { useState } from 'react'
import {
  TrendingUp, Search, ChevronRight, Zap, Star, BarChart2,
  CheckCircle, Clock, Users, Flame, BookOpen, ChevronDown, ChevronUp
} from 'lucide-react'
import { PHASES } from '../phases'
import ChannelHeader from './ChannelHeader'

// ── Mock data generators ────────────────────────────────────────────────────

const MOCK_TRENDS = [
  { id: 1, topic: 'The 5AM Club Challenge',         niche: 'Personal Development', trendScore: 0.91, velocity: 48200, engagement: 0.072, clusterSize: 5, videos: 18, lowConfidence: false },
  { id: 2, topic: 'Discipline Over Motivation',     niche: 'Mindset',              trendScore: 0.87, velocity: 41000, engagement: 0.065, clusterSize: 4, videos: 14, lowConfidence: false },
  { id: 3, topic: 'Silent Success Mode',            niche: 'Productivity',         trendScore: 0.79, velocity: 33600, engagement: 0.058, clusterSize: 3, videos: 9,  lowConfidence: false },
  { id: 4, topic: 'Stop Seeking Validation',        niche: 'Self-Improvement',     trendScore: 0.74, velocity: 28100, engagement: 0.061, clusterSize: 3, videos: 11, lowConfidence: false },
  { id: 5, topic: 'Identity-Based Habits',          niche: 'Personal Development', trendScore: 0.68, velocity: 22400, engagement: 0.049, clusterSize: 2, videos: 7,  lowConfidence: false },
  { id: 6, topic: 'Doing Less But Better',          niche: 'Productivity',         trendScore: 0.61, velocity: 18700, engagement: 0.055, clusterSize: 2, videos: 6,  lowConfidence: true  },
]

const MOCK_SCRIPTS = [
  {
    id: 'no_history',
    mode: 'Baseline',
    modeLabel: 'no_history',
    concept: 'The 5AM Club Challenge',
    hookType: 'Curiosity Gap',
    evaluatorScore: null,
    scenes: [
      { timecode: '00:00', caption: "Nobody's actually doing this at 5AM", voiceover: "Everyone says wake up at 5AM. But here's what nobody tells you — it's not about the time." },
      { timecode: '00:05', caption: 'The real reason it works', voiceover: "The 5AM club isn't a sleep schedule. It's a statement. You're telling your brain: I'm in control." },
      { timecode: '00:12', caption: 'Day 1 vs Day 30', voiceover: 'First week? Brutal. By week four, you stop needing the alarm.' },
      { timecode: '00:18', caption: 'Start tonight', voiceover: "Set your alarm for 5AM tomorrow. Don't think about it. Just do it once." },
    ],
  },
  {
    id: 'retrieval_only',
    mode: 'With Your Style',
    modeLabel: 'retrieval_only',
    concept: 'Discipline Over Motivation',
    hookType: 'Contrarian',
    evaluatorScore: null,
    scenes: [
      { timecode: '00:00', caption: 'Motivation is lying to you', voiceover: "Stop chasing motivation. It's the most overrated thing in the self-improvement space." },
      { timecode: '00:05', caption: 'Motivation vs discipline', voiceover: 'Motivation waits for you to feel good. Discipline shows up anyway.' },
      { timecode: '00:12', caption: 'The 2-minute rule', voiceover: "Don't want to work out? Commit to just two minutes. That's it. You'll almost always keep going." },
      { timecode: '00:19', caption: 'Discipline compounds', voiceover: "Six months of discipline you didn't feel like doing beats six years of waiting for motivation." },
    ],
  },
  {
    id: 'full_pipeline',
    mode: 'Full AI Pipeline',
    modeLabel: 'full_pipeline',
    concept: 'Silent Success Mode',
    hookType: 'Bold Claim',
    evaluatorScore: { overall: 7.67, styleFit: 7, hookStrength: 8, structureAdherence: 8 },
    scenes: [
      { timecode: '00:00', caption: 'The people winning say nothing', voiceover: "The most dangerous people in the room aren't the loudest. They're the ones who stopped talking and started building." },
      { timecode: '00:06', caption: 'Silent success mode', voiceover: 'Go dark. No updates. No sharing your goals. The scoreboard is your results, not your feed.' },
      { timecode: '00:13', caption: 'Energy leaks through your mouth', voiceover: "Every time you announce a goal, your brain gets a tiny dopamine hit — like you already did it. Now you won't." },
      { timecode: '00:20', caption: 'Disappear for 90 days', voiceover: 'Try it. Go quiet for 90 days. Then let your results speak.' },
    ],
  },
]

// ── Sub-components ──────────────────────────────────────────────────────────

function TrendBadge({ score }) {
  const pct = Math.round(score * 100)
  const color = pct >= 85 ? 'text-discord-green' : pct >= 70 ? 'text-discord-yellow' : 'text-discord-muted'
  return <span className={`font-bold text-sm ${color}`}>{pct}</span>
}

function TrendCard({ trend, selected, onSelect }) {
  return (
    <button
      onClick={() => onSelect(trend)}
      className={`
        w-full text-left flex items-start gap-3 px-4 py-3 rounded-lg border
        transition-all duration-150
        ${selected
          ? 'bg-discord-blurple/15 border-discord-blurple/60 shadow'
          : 'bg-discord-sidebar border-discord-faint/20 hover:border-discord-faint/50 hover:bg-discord-hover'
        }
      `}
    >
      <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-discord-input flex-shrink-0 mt-0.5">
        <Flame size={16} className={trend.trendScore >= 0.85 ? 'text-orange-400' : 'text-discord-muted'} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-discord-white font-semibold text-sm">{trend.topic}</p>
          {trend.lowConfidence && (
            <span className="px-1.5 py-0.5 bg-discord-yellow/15 text-discord-yellow text-xs rounded border border-discord-yellow/30">low conf.</span>
          )}
        </div>
        <div className="flex items-center gap-3 mt-1 flex-wrap">
          <span className="text-discord-muted text-xs flex items-center gap-1">
            <BarChart2 size={11} /> {trend.velocity.toLocaleString()} v/hr
          </span>
          <span className="text-discord-muted text-xs flex items-center gap-1">
            <Users size={11} /> {(trend.engagement * 100).toFixed(1)}% eng.
          </span>
          <span className="text-discord-muted text-xs flex items-center gap-1">
            <BookOpen size={11} /> {trend.clusterSize} similar videos
          </span>
        </div>
      </div>
      <div className="flex flex-col items-end flex-shrink-0">
        <TrendBadge score={trend.trendScore} />
        <span className="text-discord-muted text-xs">score</span>
      </div>
    </button>
  )
}

function ScriptCard({ script, selected, onSelect }) {
  const [expanded, setExpanded] = useState(false)
  const modeColors = {
    no_history:     { border: 'border-discord-muted/30',    badge: 'bg-discord-muted/20 text-discord-muted',     icon: '○' },
    retrieval_only: { border: 'border-discord-yellow/40',   badge: 'bg-discord-yellow/20 text-discord-yellow',   icon: '◑' },
    full_pipeline:  { border: 'border-discord-blurple/50',  badge: 'bg-discord-blurple/20 text-discord-blurple', icon: '●' },
  }
  const mc = modeColors[script.modeLabel]

  return (
    <div className={`
      rounded-xl border overflow-hidden transition-all duration-200
      ${selected ? 'ring-2 ring-discord-blurple ring-offset-2 ring-offset-discord-bg' : ''}
      ${mc.border} bg-discord-sidebar
    `}>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3">
        <span className="text-lg">{mc.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-discord-white font-semibold text-sm">{script.concept}</p>
            <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${mc.badge}`}>{script.mode}</span>
            <span className="px-2 py-0.5 bg-purple-500/15 text-purple-400 border border-purple-500/30 rounded-full text-xs font-semibold">{script.hookType}</span>
          </div>
          {script.evaluatorScore && (
            <div className="flex items-center gap-3 mt-1">
              <span className="text-discord-green text-xs font-semibold flex items-center gap-1">
                <Star size={11} /> {script.evaluatorScore.overall}/10 overall
              </span>
              <span className="text-discord-muted text-xs">Hook {script.evaluatorScore.hookStrength} · Structure {script.evaluatorScore.structureAdherence}</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => onSelect(script)}
            className={`
              px-3 py-1.5 rounded-md text-xs font-semibold transition-all
              ${selected
                ? 'bg-discord-blurple text-white'
                : 'bg-discord-input hover:bg-discord-blurple text-discord-muted hover:text-white'
              }
            `}
          >
            {selected ? <span className="flex items-center gap-1"><CheckCircle size={12} /> Selected</span> : 'Select'}
          </button>
          <button
            onClick={() => setExpanded(e => !e)}
            className="p-1.5 rounded text-discord-muted hover:text-discord-white hover:bg-discord-input transition-colors"
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
      </div>

      {/* Expanded scenes */}
      {expanded && (
        <div className="border-t border-discord-faint/20 px-4 pb-4 pt-3 space-y-2 animate-fade-in">
          <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide mb-3">Script Scenes</p>
          {script.scenes.map((scene, i) => (
            <div key={i} className="flex gap-3 bg-discord-input rounded-lg px-3 py-2.5">
              <div className="flex-shrink-0 flex items-center justify-center">
                <span className="text-discord-blurple font-mono text-xs font-bold">{scene.timecode}</span>
              </div>
              <div className="flex-1 min-w-0 border-l border-discord-faint/30 pl-3">
                <p className="text-discord-yellow text-xs font-semibold mb-0.5">{scene.caption}</p>
                <p className="text-discord-text text-xs leading-relaxed">{scene.voiceover}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main component ──────────────────────────────────────────────────────────

export default function IdeationPhase({
  goToPhase,
  creatorProfile,
  trends, setTrends,
  scripts, setScripts,
  selectedScript, setSelectedScript,
}) {
  const [loadingTrends, setLoadingTrends] = useState(false)
  const [loadingScripts, setLoadingScripts] = useState(false)
  const [selectedTrend, setSelectedTrend] = useState(null)

  const searchTrends = async () => {
    setLoadingTrends(true)
    setTrends([])
    setScripts([])
    setSelectedTrend(null)
    setSelectedScript(null)
    await new Promise(r => setTimeout(r, 2200))
    setTrends(MOCK_TRENDS)
    setLoadingTrends(false)
  }

  const generateScripts = async (trend) => {
    setSelectedTrend(trend)
    setLoadingScripts(true)
    setScripts([])
    setSelectedScript(null)
    await new Promise(r => setTimeout(r, 3000))
    setScripts(MOCK_SCRIPTS)
    setLoadingScripts(false)
  }

  const canProceed = !!selectedScript

  return (
    <div className="flex flex-col h-full bg-discord-bg overflow-hidden animate-fade-in">
      <ChannelHeader icon="💡" name="ideation" topic="Discover trending topics and generate 3 personalised scripts" />

      <div className="flex-1 overflow-y-auto px-6 py-6 max-w-3xl w-full mx-auto space-y-6">

        {/* Section 1: Search Trends */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-discord-white font-bold text-base flex items-center gap-2">
              <TrendingUp size={18} className="text-discord-green" />
              Trending Topics
            </h2>
            {trends.length > 0 && (
              <span className="text-discord-muted text-xs">{trends.length} clusters found</span>
            )}
          </div>

          <button
            onClick={searchTrends}
            disabled={loadingTrends}
            className={`
              flex items-center gap-2 px-5 py-3 rounded-lg font-semibold text-sm
              transition-all duration-200
              ${loadingTrends
                ? 'bg-discord-input text-discord-muted cursor-not-allowed'
                : 'bg-discord-green/20 hover:bg-discord-green text-discord-green hover:text-white border border-discord-green/40 hover:border-discord-green hover:-translate-y-0.5 shadow-sm'
              }
            `}
          >
            {loadingTrends
              ? <><span className="loading-dot"/><span className="loading-dot"/><span className="loading-dot"/><span className="ml-2">Scanning YouTube...</span></>
              : <><Search size={16} /> Search Trends</>
            }
          </button>

          {trends.length > 0 && (
            <div className="mt-4 space-y-2 animate-slide-up">
              {trends.map(t => (
                <TrendCard
                  key={t.id}
                  trend={t}
                  selected={selectedTrend?.id === t.id}
                  onSelect={generateScripts}
                />
              ))}
              <p className="text-discord-muted text-xs text-center pt-1">
                Click a trend to generate scripts matched to your style
              </p>
            </div>
          )}
        </div>

        {/* Section 2: Generated Scripts */}
        {(loadingScripts || scripts.length > 0) && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-discord-white font-bold text-base flex items-center gap-2">
                <Zap size={18} className="text-discord-blurple" />
                Generated Scripts
                {selectedTrend && (
                  <span className="text-discord-muted font-normal text-sm">
                    — {selectedTrend.topic}
                  </span>
                )}
              </h2>
              {scripts.length > 0 && <span className="text-discord-muted text-xs">3 variations</span>}
            </div>

            {loadingScripts && (
              <div className="flex flex-col items-center gap-4 py-10 animate-fade-in">
                <div className="flex gap-2">
                  <span className="loading-dot" />
                  <span className="loading-dot" />
                  <span className="loading-dot" />
                </div>
                <div className="text-center">
                  <p className="text-discord-white font-medium mb-1">Generating 3 scripts...</p>
                  <p className="text-discord-muted text-sm">Running baseline, style-matched, and full pipeline modes</p>
                </div>
              </div>
            )}

            {scripts.length > 0 && (
              <div className="space-y-3 animate-slide-up">
                {scripts.map(s => (
                  <ScriptCard
                    key={s.id}
                    script={s}
                    selected={selectedScript?.id === s.id}
                    onSelect={setSelectedScript}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* CTA */}
        {canProceed && (
          <div className="animate-slide-up pt-2">
            <button
              onClick={() => goToPhase(PHASES.EXPORT)}
              className="
                flex items-center justify-center gap-2 w-full
                px-6 py-4 rounded-lg
                bg-discord-blurple hover:bg-discord-blurple_hover
                text-white font-semibold text-base
                shadow-lg hover:shadow-discord-blurple/20 hover:shadow-xl
                transform hover:-translate-y-0.5
                transition-all duration-200
              "
            >
              Continue to Export
              <ChevronRight size={18} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
