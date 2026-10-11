import { useState } from 'react'
import { Lightbulb, TrendingUp, ChevronRight, Search, Zap } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { fetchTrendingTopics } from '../../services/api'
import { Btn, Card, Badge, ProgressSteps, SectionHeader, Page, Alert, Textarea } from '../../components/ui'

const RESEARCH_STEPS = [
  { id: 1, label: 'Analysing recent trends' },
  { id: 2, label: 'Filtering by niche' },
  { id: 3, label: 'Comparing creator relevance' },
  { id: 4, label: 'Ranking topics' },
]

export default function IdeationScreen() {
  const { creatorProfile, setSelectedTopic, setTrendingTopics, navigate } = useApp()
  const [path, setPath] = useState(null)      // 'own' | 'trend'
  const [ownIdea, setOwnIdea] = useState('')
  const [researching, setResearching] = useState(false)
  const [researchStep, setResearchStep] = useState(-1)
  const [topics, setTopics] = useState([])
  const [ownError, setOwnError] = useState('')

  const startResearch = async () => {
    setResearching(true)
    setResearchStep(0)
    setTopics([])
    const { topics: t } = await fetchTrendingTopics({
      niche: creatorProfile?.niche,
      onStep: (step) => setResearchStep(step.id - 1),
    })
    setTopics(t)
    setTrendingTopics(t)   // save to context so TopicSelectScreen can use them
    setResearching(false)
  }

  const selectTopic = (topic) => {
    setSelectedTopic(topic)
    navigate('topic-select')
  }

  const submitOwn = () => {
    if (!ownIdea.trim()) { setOwnError('Please enter your idea first.'); return }
    setSelectedTopic({
      id: 'own_' + Date.now(),
      topic: ownIdea.trim(),
      trendScore: null,
      creatorFit: null,
      signals: [],
      whyThis: 'Your own idea — personalised script generation will still apply your creator style.',
      isOwn: true,
    })
    navigate('topic-select')
  }

  return (
    <Page>
      <div className="max-w-2xl mx-auto">
        <SectionHeader
          icon={Lightbulb}
          title="Ideation"
          subtitle="Choose how you want to find your next content topic."
        />

        {/* Path selection */}
        {!path && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 animate-fadeIn">
            <Card
              hoverable
              onClick={() => setPath('own')}
              className="p-6"
            >
              <div className="w-10 h-10 rounded-xl bg-discord-blurple/15 flex items-center justify-center mb-4">
                <Lightbulb size={20} className="text-discord-blurple" />
              </div>
              <h3 className="text-discord-white font-bold text-base mb-1">I have my own idea</h3>
              <p className="text-discord-muted text-sm">Enter your topic and we'll generate creator-personalised scripts around it.</p>
              <div className="flex items-center gap-1 text-discord-blurple text-sm font-semibold mt-4">
                Use my idea <ChevronRight size={16} />
              </div>
            </Card>

            <Card
              hoverable
              onClick={() => { setPath('trend'); startResearch() }}
              className="p-6"
            >
              <div className="w-10 h-10 rounded-xl bg-discord-green/15 flex items-center justify-center mb-4">
                <TrendingUp size={20} className="text-discord-green" />
              </div>
              <h3 className="text-discord-white font-bold text-base mb-1">Find trending ideas</h3>
              <p className="text-discord-muted text-sm">Research Agent scans your niche for high-performing topics matched to your style.</p>
              <div className="flex items-center gap-1 text-discord-green text-sm font-semibold mt-4">
                Discover trends <ChevronRight size={16} />
              </div>
            </Card>
          </div>
        )}

        {/* Path A — own idea */}
        {path === 'own' && (
          <div className="animate-fadeIn">
            <button onClick={() => setPath(null)} className="text-discord-muted hover:text-discord-white text-sm mb-4 transition-colors">← Back</button>
            <Card className="p-6">
              <h3 className="text-discord-white font-semibold mb-4 flex items-center gap-2">
                <Lightbulb size={16} className="text-discord-blurple" /> Your idea
              </h3>
              <Textarea
                value={ownIdea}
                onChange={(e) => { setOwnIdea(e.target.value); setOwnError('') }}
                placeholder="e.g. Why most developers are learning the wrong things in 2025"
                rows={3}
                error={ownError}
              />
              <Btn className="mt-4 w-full" size="lg" onClick={submitOwn} icon={ChevronRight}>
                Continue to Script Generation
              </Btn>
            </Card>
          </div>
        )}

        {/* Path B — trend research */}
        {path === 'trend' && (
          <div className="animate-fadeIn">
            <button onClick={() => { setPath(null); setTopics([]); setResearching(false) }} className="text-discord-muted hover:text-discord-white text-sm mb-4 transition-colors">← Back</button>

            {/* Research in progress */}
            {researching && (
              <Card className="p-6">
                <div className="flex items-center gap-3 mb-5">
                  <Search size={18} className="text-discord-blurple animate-pulse" />
                  <h3 className="text-discord-white font-semibold">Research Agent processing…</h3>
                </div>
                <ProgressSteps steps={RESEARCH_STEPS} currentStep={researchStep} />
              </Card>
            )}

            {/* Results */}
            {!researching && topics.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <p className="text-discord-white font-semibold">{topics.length} trending topics found</p>
                  <Btn variant="ghost" size="sm" icon={Search} onClick={startResearch}>Refresh</Btn>
                </div>
                {topics.map((t) => (
                  <TopicPreviewCard key={t.id} topic={t} onSelect={() => selectTopic(t)} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </Page>
  )
}

function TopicPreviewCard({ topic, onSelect }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <Card className="p-5">
      <div className="flex items-start gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <h4 className="text-discord-white font-semibold text-sm mb-1">{topic.topic}</h4>
          <div className="flex items-center gap-3 flex-wrap">
            <ScorePill label="Trend" value={topic.trendScore} />
            <ScorePill label="Creator Fit" value={topic.creatorFit} />
          </div>
        </div>
        <Btn size="sm" onClick={onSelect} icon={Zap}>Select</Btn>
      </div>

      <p className="text-discord-muted text-xs leading-relaxed mb-3 italic">"{topic.whyThis}"</p>

      <button
        onClick={() => setExpanded(e => !e)}
        className="text-discord-blurple text-xs hover:underline"
      >
        {expanded ? 'Hide signals ↑' : `View ${topic.signals.length} supporting signals ↓`}
      </button>

      {expanded && (
        <ul className="mt-2 space-y-1">
          {topic.signals.map((s, i) => (
            <li key={i} className="flex items-start gap-2 text-discord-muted text-xs">
              <span className="text-discord-green mt-0.5">•</span> {s}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

function ScorePill({ label, value }) {
  const color = value >= 85 ? 'text-discord-green' : value >= 70 ? 'text-discord-yellow' : 'text-discord-muted'
  return (
    <span className="flex items-center gap-1 text-xs">
      <span className="text-discord-faint">{label}:</span>
      <span className={`font-bold ${color}`}>{value}/100</span>
    </span>
  )
}
