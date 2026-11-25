import { useEffect, useState } from 'react'
import { Plus, Film, ArrowRight, Play } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { getContentHistory } from '../../services/api'
import { Btn, Badge, Card, Page, SectionTitle, EmptyState, StepChip, Tile } from '../../components/ui'
import { CountUp, Stagger, StaggerItem } from '../../components/motion'

const STATUS_TONE = { Published: 'ok', Scheduled: 'info', Draft: 'muted', Processing: 'warn', Failed: 'bad' }

export default function DashboardScreen() {
  const { creatorProfile, user, navigate } = useApp()
  const [history, setHistory] = useState([])
  const [showSummary, setShowSummary] = useState(false)

  useEffect(() => {
    getContentHistory().then(({ history: h }) => setHistory(h)).catch(() => setHistory([]))
  }, [])

  if (!creatorProfile) return null
  const first = (user?.name || creatorProfile.name || '').split(' ')[0]
  const raw = creatorProfile.rawProfile || {}
  const visual = raw.visual_analysis
  const audio = raw.audio_analysis

  const stats = [
    { label: 'Published', value: creatorProfile.published },
    { label: 'Scheduled', value: creatorProfile.scheduled },
    { label: 'Drafts', value: creatorProfile.drafts },
    { label: 'Videos analysed', value: creatorProfile.analyzedVideos, hl: true },
  ]

  return (
    <Page art="dashboard">
      {/* Clapperboard hero */}
      <section className="on-dark overflow-hidden rounded-2xl bg-vh-night shadow-accent">
        <div className="clapper h-9 sm:h-11" aria-hidden="true" />
        <div className="grid gap-8 px-6 pb-9 pt-7 sm:px-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,25rem)] lg:items-center">
          <Stagger gap={0.07}>
            <StaggerItem><StepChip label="Studio · Workspace" /></StaggerItem>
            <StaggerItem as="h1" className="mt-4">
              <span className="display block text-[clamp(3.2rem,8vw,6.6rem)] text-vh-cream">Welcome back{first ? ',' : ''}</span>
              {first && <span className="display block text-[clamp(3.2rem,8vw,6.6rem)] text-vh-accent">{first}</span>}
            </StaggerItem>
            <StaggerItem as="p" className="mt-4 font-mono text-[15px] text-vh-cream">
              {creatorProfile.handle} · {creatorProfile.niche}
            </StaggerItem>
            <StaggerItem className="mt-6">
              <Btn size="lg" icon={Plus} onClick={() => navigate('ideation')}>Create new video</Btn>
            </StaggerItem>
          </Stagger>

          <Stagger as="dl" className="grid grid-cols-2 gap-3 sm:gap-4">
            {stats.map(({ label, value, hl }) => (
              <StaggerItem key={label}
                className={`flex min-h-[6.5rem] items-end justify-between gap-2 rounded-xl px-4 pb-4 pt-3 ${hl ? 'bg-vh-accent' : 'bg-vh-cream'} text-vh-night`}>
                <dt className="font-mono text-[13px]">{label}</dt>
                <dd className="display text-[3.6rem] leading-[0.8] tabular"><CountUp value={value ?? '—'} /></dd>
              </StaggerItem>
            ))}
          </Stagger>
        </div>
      </section>

      <div className="mt-12 grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        {/* Creator profile */}
        <Card className="p-6 sm:p-8">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <h2 className="display text-[clamp(2rem,3.4vw,2.6rem)]">Your creator profile</h2>
            {creatorProfile.niche && <Badge color="pop" size="md" className="max-w-[50%]"><span className="truncate">{creatorProfile.niche}</span></Badge>}
          </div>

          <div className="mt-5 flex items-center gap-4">
            <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full border-2 border-vh-night bg-vh-accent text-xl font-bold">
              {(creatorProfile.name || creatorProfile.handle || 'C').replace('@', '')[0]?.toUpperCase()}
            </span>
            <div className="min-w-0">
              <p className="truncate text-xl font-bold">{creatorProfile.name || creatorProfile.handle}</p>
              <p className="truncate font-mono text-sm">{creatorProfile.handle}</p>
            </div>
          </div>

          <dl className="mt-6 grid grid-cols-2 gap-3">
            <Tile label="Signature hook" value={creatorProfile.dominantHookType} />
            <Tile label="Structure" value={creatorProfile.dominantStructure} />
            <Tile label="Speech rate" value={audio ? `${Math.round(audio.mean_speech_rate_wpm)} wpm` : null} />
            <Tile label="Average shot" value={visual ? `${visual.mean_avg_shot_duration?.toFixed(1)} s` : null} />
          </dl>

          {creatorProfile.styleSummary && (
            <p className="mt-6 text-[16px] leading-relaxed">
              <span className={showSummary ? '' : 'line-clamp-3'}>{creatorProfile.styleSummary}</span>
              <button type="button" onClick={() => setShowSummary((v) => !v)}
                className="mt-1 font-bold underline underline-offset-4 hover:text-vh-accent2">
                {showSummary ? 'Show less' : 'Read more'}
              </button>
            </p>
          )}
        </Card>

        {/* Recent content */}
        <section>
          <SectionTitle right={history.length > 0 && (
            <button type="button" onClick={() => navigate('ideation')} className="mb-1 text-[17px] font-bold underline underline-offset-4 hover:text-vh-accent2">
              + New
            </button>
          )}>Recent content</SectionTitle>
          {history.length === 0 ? (
            <Card shadow={false}>
              <EmptyState icon={Film} title="No videos yet"
                action={<Btn variant="secondary" iconRight={ArrowRight} onClick={() => navigate('ideation')}>Start your first video</Btn>}>
                Everything you create shows up here, with its scores and status.
              </EmptyState>
            </Card>
          ) : (
            <Stagger as="ul" className="space-y-4">
              {history.map((item) => <StaggerItem as="li" key={item.id}><ContentRow item={item} /></StaggerItem>)}
            </Stagger>
          )}
        </section>
      </div>
    </Page>
  )
}

/** One video in a list: black thumbnail with a mustard play mark, title, meta, status. */
export function ContentRow({ item }) {
  const draft = item.status === 'Draft'
  const views = item.views && item.views !== '-' && item.views !== '—' ? item.views : null
  return (
    <div className={`flex items-center gap-4 rounded-xl border-2 bg-white px-4 py-4 sm:px-5 ${draft ? 'border-dashed border-vh-night' : 'border-vh-night'}`}>
      {draft
        ? <span className="h-16 w-14 shrink-0 rounded-md border-2 border-dashed border-vh-night" />
        : (
          <span className="flex h-16 w-14 shrink-0 items-center justify-center rounded-md bg-vh-night">
            <Play size={18} className="ml-0.5 text-vh-accent" fill="currentColor" />
          </span>
        )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-[17px] font-bold">{item.title}</p>
        <p className="mt-1 truncate font-mono text-[13px]">{[item.date, item.niche, views && `${views} views`].filter(Boolean).join(' · ')}</p>
      </div>
      <Badge color={STATUS_TONE[item.status] || 'muted'} size="md">{item.status}</Badge>
    </div>
  )
}
