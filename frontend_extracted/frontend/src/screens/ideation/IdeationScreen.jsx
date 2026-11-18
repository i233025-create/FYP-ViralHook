import { useState } from 'react'
import { ArrowRight, ArrowLeft, RefreshCw, ChevronDown, Clock, PenLine, BarChart3, Radar } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { fetchTrendingTopics } from '../../services/api'
import { Btn, Card, Badge, Page, PageHero, Alert, Textarea, SectionTitle, scoreTone } from '../../components/ui'
import JobProgress from '../../components/JobProgress'
import { Stagger, StaggerItem } from '../../components/motion'
import { IdeaInputPreview, OptionCard, OptionGrid, TrendListPreview } from '../../components/previews'

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
  const [researchError, setResearchError] = useState('')

  const startResearch = async () => {
    setResearching(true)
    setResearchStep(0)
    setTopics([])
    setResearchError('')
    try {
      const { topics: t } = await fetchTrendingTopics({
        niche: creatorProfile?.niche,
        onStep: (step) => setResearchStep(step.id - 1),
      })
      setTopics(t)
      setTrendingTopics(t)
    } catch (err) {
      setResearchError(err?.message || 'Research failed. Check that the backend is running.')
    }
    setResearching(false)
  }

  const selectTopic = (topic) => {
    setSelectedTopic(topic)
    navigate('topic-select')
  }

  const submitOwn = () => {
    if (!ownIdea.trim()) { setOwnError('Write your idea first.'); return }
    setSelectedTopic({
      id: 'own_' + Date.now(),
      topic: ownIdea.trim(),
      trendScore: null,
      creatorFit: null,
      signals: [],
      whyThis: 'Your own idea — scripts are still written in your style.',
      isOwn: true,
    })
    navigate('topic-select')
  }

  const back = () => { setPath(null); setTopics([]); setResearching(false); setResearchError('') }

  return (
    <Page art="ideation">
      <PageHero
        step="01"
        label="Ideation"
        title={["What's", 'Next?']}
        lead={`Bring your own idea or let the research agent find what's working in ${creatorProfile?.niche || 'your niche'} right now — measured on real videos from the last 14 days.`}
      />

      {!path && (
        <OptionGrid>
          <OptionCard
            number="01"
            kicker="Seconds"
            title="I have my own idea"
            line="Write your topic; scripts are written around it in your own voice."
            preview={<IdeaInputPreview />}
            specs={[
              { icon: Clock, label: 'Takes', value: 'Seconds' },
              { icon: PenLine, label: 'You give', value: 'One line about the video' },
            ]}
            bestFor="When you already know what to post"
            cta="Use my idea"
            onClick={() => setPath('own')}
          />
          <OptionCard
            number="02"
            kicker="About a minute"
            title="Find trending ideas"
            line="The research agent ranks what's working in your niche, measured on real videos."
            preview={<TrendListPreview />}
            specs={[
              { icon: Clock, label: 'Takes', value: 'About a minute' },
              { icon: BarChart3, label: 'You get', value: 'Ranked topics with evidence' },
            ]}
            bestFor="When you need something that's working now"
            cta="Find trends"
            onClick={() => { setPath('trend'); startResearch() }}
          />
        </OptionGrid>
      )}

      {path === 'own' && (
        <div>
          <BackLink onClick={back} />
          <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
          <Card className="p-6 sm:p-8">
            <h2 className="display mb-4 text-[2.4rem]">Your idea</h2>
            <Textarea
              label="One line about the video"
              value={ownIdea}
              onChange={(e) => { setOwnIdea(e.target.value); setOwnError('') }}
              placeholder="e.g. Rs 50 vs Rs 500 kulfi in Sahiwal — is the expensive one worth it?"
              rows={4}
              error={ownError}
            />
            <div className="mt-5 flex justify-end">
              <Btn size="lg" iconRight={ArrowRight} onClick={submitOwn}>Continue</Btn>
            </div>
          </Card>
          <Card tone="dark" className="p-6 sm:p-8">
            <p className="font-mono text-[13px] font-semibold uppercase tracking-[0.08em] text-vh-accent">What makes a good idea</p>
            <ol className="mt-4 space-y-3.5">
              {['One clear question or claim', 'Specific: a place, a price, a number', 'Something you can show on camera'].map((t, i) => (
                <li key={t} className="flex items-center gap-4">
                  <span className="display w-9 text-[2rem] leading-none text-vh-accent">{String(i + 1).padStart(2, '0')}</span>
                  <span className="text-[16px] font-semibold">{t}</span>
                </li>
              ))}
            </ol>
          </Card>
          </div>
        </div>
      )}

      {path === 'trend' && (
        <div>
          <BackLink onClick={back} />

          {researching && (
            <JobProgress icon={Radar} title="Researching your niche" steps={RESEARCH_STEPS} currentStep={researchStep}
              hint="Scanning YouTube Shorts from the last 14 days and ranking topics by real performance." />
          )}

          {!researching && researchError && (
            <div className="max-w-xl space-y-3">
              <Alert type="error">{researchError}</Alert>
              <Btn variant="secondary" icon={RefreshCw} onClick={startResearch}>Try again</Btn>
            </div>
          )}

          {!researching && topics.length > 0 && (
            <>
              <SectionTitle right={<Btn variant="secondary" size="sm" icon={RefreshCw} onClick={startResearch}>Refresh</Btn>}>
                {topics.length} trending topics
              </SectionTitle>
              <p className="-mt-2 mb-5 font-mono text-[13px]">YouTube Shorts · last 14 days · ranked by real performance</p>
              <Stagger className="space-y-4">
                {topics.map((t, i) => (
                  <StaggerItem key={t.id}><TopicRow rank={i + 1} topic={t} onSelect={() => selectTopic(t)} /></StaggerItem>
                ))}
              </Stagger>
            </>
          )}
        </div>
      )}
    </Page>
  )
}

function BackLink({ onClick }) {
  return (
    <button type="button" onClick={onClick} className="mb-6 inline-flex items-center gap-1.5 text-[15px] font-semibold underline-offset-4 hover:underline">
      <ArrowLeft size={16} /> Choose another way
    </button>
  )
}

function Score({ label, value }) {
  const tone = scoreTone(value)
  return (
    <div className="text-right">
      <p className={`display text-[2.4rem] leading-[0.85] tabular ${tone === 'bad' ? 'text-vh-accent2' : ''}`}>{value ?? '—'}</p>
      <p className="mt-1 font-mono text-[12px]">{label}</p>
    </div>
  )
}

function TopicRow({ rank, topic, onSelect }) {
  const [open, setOpen] = useState(false)
  return (
    <Card shadow={false} className="p-5 sm:p-6">
      <div className="flex items-start gap-5">
        <span className="display w-12 shrink-0 text-[3rem] leading-[0.85] text-vh-accent2 tabular">{String(rank).padStart(2, '0')}</span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[18px] font-bold">{topic.topic}</h3>
            {topic.lowConfidence && <Badge color="warn">Low confidence</Badge>}
          </div>
          {topic.whyThis && <p className="mt-1.5 text-[15px] leading-relaxed">{topic.whyThis}</p>}
          {topic.signals?.length > 0 && (
            <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open}
              className="mt-3 inline-flex items-center gap-1 text-[14px] font-bold underline underline-offset-4">
              {topic.signals.length} supporting signals
              <ChevronDown size={14} strokeWidth={3} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
            </button>
          )}
          {open && (
            <ul className="mt-3 space-y-1.5 border-l-4 border-vh-accent pl-3">
              {topic.signals.map((s, i) => <li key={i} className="text-[14px] leading-relaxed">{s}</li>)}
            </ul>
          )}
        </div>
        <div className="hidden shrink-0 items-start gap-6 sm:flex">
          <Score label="Trend" value={topic.trendScore} />
          <Score label="Fit" value={topic.creatorFit} />
        </div>
        <Btn size="sm" onClick={onSelect} iconRight={ArrowRight} className="shrink-0">Select</Btn>
      </div>
    </Card>
  )
}
