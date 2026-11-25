import { useState, useRef } from 'react'
import { Upload, Film, X, ArrowLeft, ArrowRight, AudioWaveform, Mic2, ListTree, Palette, Timer, Gauge, Scissors, Users } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { processCreatorVideos } from '../../services/api'
import { Btn, Card, Input, Select, Alert, Badge, Page, PageHero, ActionBar, Stat, Tile } from '../../components/ui'
import { Stagger, StaggerItem } from '../../components/motion'
import JobProgress from '../../components/JobProgress'
import { NICHES } from '../../data/mockData'
import { stylePreviewProfile } from '../../dev/previewState'

const PROCESS_STEPS = [
  { id: 1, label: 'Uploading videos' },
  { id: 2, label: 'Transcribing & extracting text style' },
  { id: 3, label: 'Building your knowledge base' },
  { id: 4, label: 'Visual & audio analysis' },
  { id: 5, label: 'Generating your creator profile' },
]
const MAX_VIDEOS = 10
const LEARN = [[Mic2, 'How you talk'], [ListTree, 'Your hooks and structure'], [Gauge, 'Speaking speed and energy'], [Scissors, 'Shot length and look']]
// development preview of the result screen (?preview=style-ready)
const STYLE_PREVIEW = stylePreviewProfile()

export default function ExperiencedCreatorScreen() {
  const { setCreatorProfile, navigate } = useApp()
  const fileRef = useRef(null)
  const [handle, setHandle] = useState('')
  const [niche, setNiche] = useState(NICHES[0])
  const [videos, setVideos] = useState([])
  const [phase, setPhase] = useState(STYLE_PREVIEW ? 'done' : 'form') // 'form' | 'processing' | 'done'
  const [currentStep, setCurrentStep] = useState(-1)
  const [stepDetail, setStepDetail] = useState('')
  const [profile, setProfile] = useState(STYLE_PREVIEW)
  const [error, setError] = useState('')
  const [dragging, setDragging] = useState(false)
  const [showFull, setShowFull] = useState(false)

  const addVideos = (files) => {
    const valid = Array.from(files).filter((f) => f.type.startsWith('video/'))
    if (!valid.length) { setError('Please upload video files only.'); return }
    setError('')
    setVideos((v) => [...v, ...valid.map((f) => ({ id: crypto.randomUUID(), file: f, name: f.name, size: f.size }))].slice(0, MAX_VIDEOS))
  }
  const removeVideo = (id) => setVideos((v) => v.filter((x) => x.id !== id))
  const fmt = (b) => (b < 1e6 ? `${(b / 1024).toFixed(0)} KB` : `${(b / 1e6).toFixed(1)} MB`)

  const startProcessing = async () => {
    if (!handle.trim()) { setError('Please enter your social handle.'); return }
    if (videos.length === 0) { setError('Please upload at least one video.'); return }
    setError('')
    setPhase('processing')
    setCurrentStep(0)
    try {
      const { profile: p } = await processCreatorVideos({
        files: videos.map((v) => v.file), handle, niche,
        onStep: (step) => { setCurrentStep(step.id - 1); setStepDetail(step.detail || '') },
      })
      setProfile(p)
      setPhase('done')
    } catch (err) {
      setError(err?.message || 'Processing failed. Please try again.')
      setPhase('form')
    }
  }

  const finish = () => {
    setCreatorProfile(profile)
    navigate('dashboard')
  }

  // ── Done: the learned style, organised ─────────────────────────────────────
  if (phase === 'done' && profile) {
    const raw = profile.rawProfile || {}
    const audio = raw.audio_analysis
    const visual = raw.visual_analysis
    const hooks = raw.signature_hooks?.length ? raw.signature_hooks : [profile.dominantHookType].filter(Boolean)
    const topics = raw.recurring_topics || []
    const [lead, ...rest] = (profile.styleSummary || '').split(/(?<=\.)\s+/)
    const tiles = [
      [Mic2, 'Signature hook', profile.dominantHookType],
      [ListTree, 'Structure', profile.dominantStructure],
      [Palette, 'Tone', raw.dominant_tone],
      [Timer, 'Pacing', raw.avg_pacing || visual?.visual_pacing],
      [Gauge, 'Speech rate', audio ? `${Math.round(audio.mean_speech_rate_wpm)} wpm` : null],
      [Scissors, 'Average shot', visual ? `${visual.mean_avg_shot_duration?.toFixed(1)} s` : null],
    ]

    return (
      <Page art="onboarding">
        <PageHero
          label="Profile ready"
          title={['Your', 'Style']}
          topic={profile.handle}
          lead={`Learned from ${profile.analyzedVideos} video${profile.analyzedVideos === 1 ? '' : 's'}. Every script you generate is written and scored against this profile.`}
        />

        {/* style fingerprint */}
        <Card className="p-6 sm:p-8">
          <h2 className="display text-[2.4rem]">Your style at a glance</h2>
          <Stagger as="dl" className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-3">
            {tiles.map(([Icon, label, value]) => (
              <StaggerItem key={label}><Tile icon={Icon} label={label} value={value} /></StaggerItem>
            ))}
          </Stagger>
        </Card>

        <div className="mt-8 grid items-start gap-8 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
          {/* summary: first sentence as the headline, the rest collapsible */}
          <Card tone="dark" className="p-6 sm:p-9">
            <p className="font-mono text-[13px] font-semibold uppercase tracking-[0.08em] text-vh-accent">How you come across</p>
            <p className="display mt-4 text-[clamp(1.9rem,3.2vw,2.7rem)] leading-[1.04]">{lead}</p>
            {rest.length > 0 && (
              <>
                <p className={`mt-4 text-[16px] leading-relaxed ${showFull ? '' : 'line-clamp-3'}`}>{rest.join(' ')}</p>
                <button type="button" onClick={() => setShowFull((v) => !v)}
                  className="mt-2 text-[15px] font-bold text-vh-accent underline underline-offset-4">
                  {showFull ? 'Show less' : 'Read more'}
                </button>
              </>
            )}
          </Card>

          <div className="space-y-6">
            {hooks.length > 0 && (
              <Card shadow={false} className="p-6">
                <h3 className="display text-[1.9rem]">Hooks you use</h3>
                <div className="mt-3 flex flex-wrap gap-2">
                  {hooks.map((h, i) => <Badge key={h} size="md" color={i === 0 ? 'accent' : 'muted'}>{i === 0 && '★ '}{h}</Badge>)}
                </div>
              </Card>
            )}
            {topics.length > 0 && (
              <Card shadow={false} className="p-6">
                <h3 className="display text-[1.9rem]">You talk about</h3>
                <ul className="mt-3 flex flex-wrap gap-2">
                  {topics.map((t) => (
                    <li key={t} className="rounded-full border-2 border-vh-night px-3 py-1 text-[14px] font-semibold">{t}</li>
                  ))}
                </ul>
              </Card>
            )}
            {raw.target_audience && (
              <Card shadow={false} className="p-6">
                <h3 className="display flex items-center gap-2 text-[1.9rem]"><Users size={20} />Your audience</h3>
                <p className="mt-2 text-[15px] leading-relaxed">{raw.target_audience}</p>
              </Card>
            )}
          </div>
        </div>

        <ActionBar actions={<Btn size="lg" iconRight={ArrowRight} onClick={finish}>Go to studio</Btn>}>
          <Stat label="Videos analysed" value={profile.analyzedVideos} />
          <Stat label="Niche" value={profile.niche} />
        </ActionBar>
      </Page>
    )
  }

  // ── Processing ──────────────────────────────────────────────────────────────
  if (phase === 'processing') {
    return (
      <Page art="onboarding">
        <PageHero
          label="Building your profile"
          title={['Learning', 'Your style']}
          lead={`${videos.length} video${videos.length !== 1 ? 's' : ''} queued. This takes a few minutes per video — keep this tab open.`}
        />
        <JobProgress icon={AudioWaveform} title="Building your creator profile" steps={PROCESS_STEPS}
          currentStep={currentStep} detail={stepDetail}
          hint="A few minutes per video. Keep this tab open — your profile appears as soon as it's ready." />
      </Page>
    )
  }

  // ── Form ────────────────────────────────────────────────────────────────────
  return (
    <Page art="onboarding">
      <button type="button" onClick={() => navigate('creator-type')}
        className="mb-6 inline-flex items-center gap-1.5 text-[15px] font-semibold underline-offset-4 hover:underline">
        <ArrowLeft size={16} /> All options
      </button>
      <PageHero
        step="02"
        label="Set up"
        title={['Teach us', 'Your style']}
        lead="Upload a few of your best past videos. We transcribe them and measure how you speak, hook and cut."
      />

      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Card className="p-6 sm:p-8">
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Social handle" value={handle} onChange={(e) => setHandle(e.target.value)} placeholder="@yourhandle" required />
            <Select label="Primary niche" value={niche} onChange={(e) => setNiche(e.target.value)} options={NICHES} />
          </div>

          <div
            role="button"
            tabIndex={0}
            onClick={() => fileRef.current?.click()}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && fileRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); addVideos(e.dataTransfer.files) }}
            className={`mt-6 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-vh-night px-6 py-12 text-center transition-colors
              ${dragging ? 'bg-vh-accent/25' : 'bg-vh-cream hover:bg-vh-accent/10'}`}
          >
            <input ref={fileRef} type="file" accept="video/*" multiple onChange={(e) => addVideos(e.target.files)} />
            <Upload size={34} strokeWidth={2.25} className="mb-4" />
            <p className="display text-[clamp(2.1rem,3.4vw,2.8rem)]">Drop videos here</p>
            <p className="mt-1 text-[16px]">or <span className="font-bold underline underline-offset-4">browse</span> from your device</p>
            <p className="mt-3 font-mono text-[13px]">MP4, MOV or AVI · up to {MAX_VIDEOS} videos</p>
          </div>

          {videos.length > 0 && (
            <ul className="mt-5 space-y-2">
              {videos.map((v) => (
                <li key={v.id} className="flex items-center gap-3 rounded-xl border-2 border-vh-night px-4 py-2.5">
                  <span className="flex h-9 w-8 shrink-0 items-center justify-center rounded bg-vh-night"><Film size={14} className="text-vh-accent" /></span>
                  <span className="flex-1 truncate text-[15px] font-semibold">{v.name}</span>
                  <span className="font-mono text-[12px] tabular">{fmt(v.size)}</span>
                  <button type="button" onClick={() => removeVideo(v.id)} aria-label={`Remove ${v.name}`}
                    className="rounded p-1 hover:bg-vh-accent2 hover:text-white"><X size={16} /></button>
                </li>
              ))}
            </ul>
          )}

          {error && <div className="mt-4"><Alert type="error">{error}</Alert></div>}

          <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
            <p className="font-mono text-[13px]">{videos.length}/{MAX_VIDEOS} videos added</p>
            <Btn size="lg" iconRight={ArrowRight} onClick={startProcessing} disabled={!videos.length || !handle}>
              Analyse my videos
            </Btn>
          </div>
        </Card>

        <Card tone="dark" className="p-6 sm:p-8">
          <p className="font-mono text-[13px] font-semibold uppercase tracking-[0.08em] text-vh-accent">What we learn</p>
          <h2 className="display mt-3 text-[2.6rem]">{videos.length ? `${videos.length} video${videos.length > 1 ? 's' : ''} ready` : 'Your style, measured'}</h2>
          <ol className="mt-5 space-y-3.5">
            {LEARN.map(([Icon, label], i) => (
              <li key={label} className="flex items-center gap-4">
                <span className="display w-9 text-[2rem] leading-none text-vh-accent">{String(i + 1).padStart(2, '0')}</span>
                <Icon size={18} className="shrink-0" />
                <span className="text-[17px] font-semibold">{label}</span>
              </li>
            ))}
          </ol>
        </Card>
      </div>
    </Page>
  )
}
