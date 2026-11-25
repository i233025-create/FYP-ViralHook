import { useState, useEffect, useRef } from 'react'
import { Edit2, RefreshCw, ArrowRight, Play, Images, Clapperboard } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { generateAIVideo, regenerateVisual, photoUrl, VIDEO_STEPS } from '../../services/api'
import CreatorPhotosStep from './CreatorPhotosStep'
import {
  Btn, Card, Badge, Page, PageHero, Modal, Input, Textarea, ActionBar, Stat, Segmented,
  SegmentTag, SEGMENT_BAR, InfoTip,
} from '../../components/ui'
import JobProgress from '../../components/JobProgress'
import { Stagger, StaggerItem } from '../../components/motion'
import { MOCK_VISUAL_ASSETS } from '../../data/mockData'

const pct = (v) => (v === null || v === undefined ? '—' : `${Math.round(v * 100)}`)

const SOURCE_LABEL = { creator: 'your photo', pexels: 'stock', sdxl: 'generated', placeholder: 'placeholder' }

/** How a scene's shots were filled, e.g. "your photo · generated". */
function sceneSources(scene) {
  const seen = []
  for (const sh of scene.shots || []) {
    const label = SOURCE_LABEL[sh.source] || sh.source
    if (label && !seen.includes(label)) seen.push(label)
  }
  return seen.join(' · ')
}

const creatorShot = (scene) => (scene.shots || []).find((sh) => sh.source === 'creator')
const MODES = [{ value: 'personalised', label: 'Personalised' }, { value: 'generic', label: 'Generic' }]

export default function VideoGenScreen() {
  const { productionPlan, videoTimeline, setVideoTimeline, videoResult, setVideoResult, selectedTopic, navigate } = useApp()
  const [phase, setPhase] = useState(videoTimeline ? 'done' : 'setup')
  const [step, setStep] = useState(0)
  const [stepDetail, setStepDetail] = useState('')
  const [error, setError] = useState(null)
  const [mode, setMode] = useState(videoResult?.mode || 'personalised')
  const videoRef = useRef(null)
  const [timeline, setTimeline] = useState(videoTimeline || [])
  const [selected, setSelected] = useState(null)
  const [editModal, setEditModal] = useState(false)
  const [editForm, setEditForm] = useState({})
  const [updating, setUpdating] = useState(false)
  const [assetModal, setAssetModal] = useState(false)
  const [regenerating, setRegenerating] = useState(false)
  // Creator photos (E3): review = SigLIP suggestions, choices = creator's pick per scene,
  // photoRun = what the last render used (kept for Regenerate / mode switch)
  const [review, setReview] = useState(null)
  const [choices, setChoices] = useState({})
  const [photoRun, setPhotoRun] = useState(videoResult?.photoRun || null)

  useEffect(() => {
    if (videoTimeline) setTimeline(videoTimeline)
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  const startFromPhotos = (run) => { setPhotoRun(run); runGeneration(mode, run) }

  const runGeneration = async (runMode = mode, run = photoRun) => {
    setPhase('generating')
    setStep(0)
    setStepDetail('')
    setError(null)
    setSelected(null)
    try {
      const result = await generateAIVideo({
        plan: productionPlan,
        mode: runMode,
        assetLibraryId: run?.libraryId || null,
        sceneAssets: run?.sceneAssets || null,
        onStep: (s) => { setStep(s.id - 1); setStepDetail(s.detail || '') },
      })
      setTimeline(result.timeline)
      setVideoTimeline(result.timeline)
      setVideoResult({ videoUrl: result.videoUrl, evaluation: result.evaluation, mode: result.mode, photoRun: run })
      setPhase('done')
    } catch (e) {
      setError(e.message)
    }
  }

  const switchMode = (m) => { if (m !== mode) { setMode(m); runGeneration(m) } }

  const selectScene = (scene) => {
    setSelected(scene)
    if (videoRef.current && scene.start !== undefined) {
      videoRef.current.currentTime = scene.start
      videoRef.current.play().catch(() => {})
    }
  }

  const openEdit = (scene) => { setEditForm({ ...scene }); setEditModal(true) }

  const saveEdit = async () => {
    setUpdating(true)
    await new Promise((r) => setTimeout(r, 800))
    setTimeline((prev) => prev.map((s) => (s.id === editForm.id ? { ...editForm } : s)))
    if (selected?.id === editForm.id) setSelected({ ...editForm })
    setUpdating(false)
    setEditModal(false)
  }

  const swapAsset = async (asset) => {
    setAssetModal(false)
    setRegenerating(true)
    await regenerateVisual({ sceneId: selected.id })
    setTimeline((prev) => prev.map((s) => (s.id === selected.id ? { ...s, visual: asset.label } : s)))
    setSelected((s) => (s ? { ...s, visual: asset.label } : s))
    setRegenerating(false)
  }

  const creatorPhotoUrl = (name) =>
    photoRun?.libraryId && name ? photoUrl(`/assets/${photoRun.libraryId}/file/${encodeURIComponent(name)}`) : null

  // ── Creator photos: upload + review ─────────────────────────────────────────
  if (phase === 'setup') {
    return (
      <CreatorPhotosStep plan={productionPlan} mode={mode} review={review} setReview={setReview}
        choices={choices} setChoices={setChoices} onGenerate={startFromPhotos} topic={selectedTopic?.topic}
        onBack={videoTimeline ? () => setPhase('done') : null} />
    )
  }

  // ── Rendering ───────────────────────────────────────────────────────────────
  if (phase === 'generating') {
    return (
      <Page art="video">
        <PageHero step="04" label="AI video" title={['Rendering', 'Your video']} topic={selectedTopic?.topic}
          lead={`${mode === 'personalised' ? 'Personalised' : 'Generic baseline'} edit: voiceover → shots → visuals → render. This takes a few minutes on the GPU.`} />
        <JobProgress icon={Clapperboard} title="Rendering your video" steps={VIDEO_STEPS} currentStep={step}
          detail={stepDetail} error={error}
          action={<Btn size="sm" variant="secondary" icon={RefreshCw} onClick={() => runGeneration()}>Try again</Btn>}
          hint="Voiceover → shots → visuals → render. A few minutes on the GPU." />
      </Page>
    )
  }

  // ── Preview ─────────────────────────────────────────────────────────────────
  const ev = videoResult?.evaluation
  const totalEnd = timeline.length ? timeline[timeline.length - 1].endTime : '—'

  return (
    <Page art="video">
      <PageHero
        step="04"
        label="AI video"
        title={['Your', 'Cut']}
        topic={selectedTopic?.topic}
        lead="Play it through, click any scene to jump to it, then edit or swap its visual."
        aside={
          <div className="flex flex-wrap items-center gap-2">
            <Segmented label="Edit mode" options={MODES} value={mode} onChange={switchMode} size="sm" />
            <Btn variant="secondary" size="sm" icon={Images} onClick={() => setPhase('setup')}>Your photos</Btn>
            <Btn variant="secondary" size="sm" icon={RefreshCw} onClick={() => runGeneration()}>Re-render</Btn>
          </div>
        }
      />

      <div className="grid gap-8 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
        {/* Player */}
        <div>
          <div className="relative mx-auto flex aspect-[9/16] w-full max-w-[16rem] items-center justify-center overflow-hidden rounded-2xl bg-vh-night shadow-accent sm:max-w-[19rem] lg:max-w-none">
            {videoResult?.videoUrl ? (
              <video ref={videoRef} src={videoResult.videoUrl} controls playsInline className="h-full w-full object-contain" />
            ) : selected ? (
              <>
                <div className={`absolute inset-0 opacity-25 ${SEGMENT_BAR[selected.segment] || 'bg-vh-frame'}`} />
                <div className="relative text-center">
                  <span className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-vh-accent text-vh-night">
                    <Play size={26} className="ml-1" fill="currentColor" />
                  </span>
                  <SegmentTag segment={selected.segment} />
                  <p className="mt-1.5 font-mono text-[12px] text-vh-cream">{selected.startTime}–{selected.endTime}</p>
                </div>
                {selected.caption && (
                  <p className="absolute inset-x-4 bottom-10 text-center">
                    <span className="display inline-block rounded bg-vh-night px-3 py-1 text-[1.6rem] text-vh-cream">{selected.caption}</span>
                  </p>
                )}
              </>
            ) : (
              <div className="px-6 text-center">
                <span className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-vh-accent text-vh-night">
                  <Play size={26} className="ml-1" fill="currentColor" />
                </span>
                <p className="font-mono text-[13px] text-vh-cream">Select a scene to preview</p>
              </div>
            )}
          </div>
        </div>

        {/* Scenes + selected scene */}
        <div className="min-w-0">
          <h2 className="display mb-4 text-[2.4rem]">{timeline.length} scenes · {totalEnd}</h2>
          <Stagger as="ol" gap={0.05} className="space-y-3">
            {timeline.map((scene, i) => {
              const on = selected?.id === scene.id
              const photo = creatorPhotoUrl(creatorShot(scene)?.assetName)
              return (
                <StaggerItem as="li" key={scene.id}>
                  <button type="button" onClick={() => selectScene(scene)} aria-pressed={on}
                    className={`flex w-full items-center gap-4 rounded-xl border-2 border-vh-night bg-white px-4 py-3 text-left transition-[transform,box-shadow] duration-200
                      ${on ? 'shadow-accent' : 'hover:-translate-y-0.5 hover:shadow-hard-sm'}`}>
                    <span className="display w-8 shrink-0 text-[2rem] leading-none text-vh-accent2 tabular">{String(i + 1).padStart(2, '0')}</span>
                    {photo
                      ? <img src={photo} alt="" className="h-12 w-12 shrink-0 rounded-md border-2 border-vh-night object-cover" />
                      : <span className={`h-12 w-12 shrink-0 rounded-md ${SEGMENT_BAR[scene.segment] || 'bg-vh-cream'}`} />}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <SegmentTag segment={scene.segment} />
                        <span className="font-mono text-[12px]">{scene.startTime}–{scene.endTime}</span>
                      </div>
                      <p className="mt-1 truncate text-[15px] font-medium">{scene.voiceover}</p>
                    </div>
                    {sceneSources(scene) && (
                      <span className={`hidden shrink-0 font-mono text-[12px] sm:block ${creatorShot(scene) ? 'font-bold' : ''}`}>
                        {sceneSources(scene)}
                      </span>
                    )}
                  </button>
                </StaggerItem>
              )
            })}
          </Stagger>

          {selected && (
            <Card className="mt-6 p-5 sm:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <SegmentTag segment={selected.segment} />
                  <p className="mt-2 text-[16px] font-medium leading-relaxed">{selected.voiceover}</p>
                  {selected.visual && <p className="mt-1 font-mono text-[13px]">Visual: {selected.visual}</p>}
                </div>
                <div className="flex gap-2">
                  <Btn variant="secondary" size="sm" icon={Edit2} onClick={() => openEdit(selected)}>Edit</Btn>
                  <Btn variant="secondary" size="sm" icon={RefreshCw} loading={regenerating} onClick={() => setAssetModal(true)}>
                    {regenerating ? 'Swapping…' : 'Swap visual'}
                  </Btn>
                </div>
              </div>
              {selected.shots?.length > 0 && (
                <ul className="mt-4 space-y-2 border-t-2 border-vh-night/10 pt-4">
                  {selected.shots.map((sh, i) => (
                    <li key={i} className="flex items-center gap-2.5 text-[13px]">
                      {sh.source === 'creator' && creatorPhotoUrl(sh.assetName)
                        ? <img src={creatorPhotoUrl(sh.assetName)} alt="" className="h-9 w-9 rounded object-cover" />
                        : <span className="h-9 w-9 rounded bg-vh-cream" />}
                      <Badge color={sh.source === 'creator' ? 'ok' : 'muted'}>{SOURCE_LABEL[sh.source] || sh.source}</Badge>
                      <span className="flex-1 truncate">{sh.query}</span>
                      <span className="font-mono">
                        {sh.source === 'creator'
                          ? `fit ${sh.assetScore?.toFixed(3) ?? '—'}`
                          : sh.clipScore !== null && sh.clipScore !== undefined ? `CLIP ${sh.clipScore.toFixed(3)}` : ''}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {updating && <p className="mt-3 font-mono text-[13px]">Updating the timeline…</p>}
            </Card>
          )}
        </div>
      </div>

      {ev?.scores && (
        <Card tone="dark" as="section" className="mt-12 p-6 sm:p-8">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="display text-[2.4rem]">Measured style fidelity</h2>
            <span className="font-mono text-[13px] uppercase text-vh-accent">{videoResult.mode}</span>
          </div>
          <dl className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-5">
            <Metric label="Style fidelity" value={pct(ev.scores.style_fidelity)} tip="Overall match between this video and your measured style." />
            <Metric label="Visual look" value={pct(ev.scores.visual_match)}
              hint={ev.visual ? `CLIP ${ev.visual.creator_similarity} vs your own ${ev.visual.creator_self_similarity}` : 'no visual profile yet'} />
            <Metric label="Cut pacing" value={pct(ev.scores.pacing_match)}
              hint={`${ev.measured?.avg_shot_duration ?? '—'} s vs ${ev.target?.avg_shot_duration ?? '—'} s`} />
            <Metric label="Speech rate" value={pct(ev.scores.speech_rate_match)}
              hint={`${ev.measured?.speech_rate_wpm ?? '—'} vs ${ev.target?.speech_rate_wpm ?? '—'} wpm`} />
            <Metric label="Picture–voice match" value={ev.clip_alignment?.mean?.toFixed(3) ?? '—'}
              tip="How well each scene's picture matches what the voiceover says (CLIP)." />
          </dl>
        </Card>
      )}

      <ActionBar actions={<Btn size="lg" iconRight={ArrowRight} onClick={() => navigate('publish')}>Continue to publish</Btn>}>
        <Stat label="Mode" value={mode === 'personalised' ? 'Personalised' : 'Generic'} />
        <Stat label="Duration" value={totalEnd} />
        <Stat label="Your photos" value={photoRun ? `${Object.values(photoRun.sceneAssets || {}).filter(Boolean).length} scenes` : 'None'} />
      </ActionBar>

      <Modal open={editModal} onClose={() => setEditModal(false)} title="Edit scene">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Input label="Start" value={editForm.startTime || ''} onChange={(e) => setEditForm((f) => ({ ...f, startTime: e.target.value }))} />
            <Input label="End" value={editForm.endTime || ''} onChange={(e) => setEditForm((f) => ({ ...f, endTime: e.target.value }))} />
          </div>
          <Textarea label="Voiceover / subtitle" value={editForm.voiceover || ''} rows={3}
            onChange={(e) => setEditForm((f) => ({ ...f, voiceover: e.target.value }))} />
          <Input label="Caption overlay" value={editForm.caption || ''} onChange={(e) => setEditForm((f) => ({ ...f, caption: e.target.value }))} />
          <div className="flex justify-end gap-2 pt-1">
            <Btn variant="ghost" onClick={() => setEditModal(false)}>Cancel</Btn>
            <Btn onClick={saveEdit} loading={updating}>Save scene</Btn>
          </div>
        </div>
      </Modal>

      <Modal open={assetModal} onClose={() => setAssetModal(false)} title="Choose a visual">
        <div className="space-y-2">
          {MOCK_VISUAL_ASSETS.map((a) => (
            <button key={a.id} type="button" onClick={() => swapAsset(a)}
              className="flex w-full items-center gap-3 rounded-xl border-2 border-vh-night bg-white px-4 py-3 text-left text-[15px] font-semibold hover:bg-vh-accent">
              <span className="h-8 w-8 shrink-0 rounded border-2 border-vh-night" style={{ backgroundColor: a.color }} />
              {a.label}
            </button>
          ))}
        </div>
      </Modal>
    </Page>
  )
}

function Metric({ label, value, hint, tip }) {
  return (
    <div className="rounded-xl bg-vh-frame px-4 py-4">
      <dt className="flex items-center gap-1 font-mono text-[12px]">{label}{tip && <InfoTip text={tip} />}</dt>
      <dd className="display mt-2 text-[2.6rem] leading-[0.85] text-vh-accent tabular">{value}</dd>
      {hint && <p className="mt-1.5 truncate font-mono text-[11px]">{hint}</p>}
    </div>
  )
}
