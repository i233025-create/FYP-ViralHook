import { useState, useEffect, useRef } from 'react'
import { Sparkles, CheckCircle, Clock, Edit2, RefreshCw, ChevronRight, Play, Images } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { generateAIVideo, regenerateVisual, photoUrl, VIDEO_STEPS } from '../../services/api'
import CreatorPhotosStep from './CreatorPhotosStep'
import { Btn, Card, Badge, ProgressSteps, SectionHeader, Page, Modal, Input, Textarea, Alert } from '../../components/ui'
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

export default function VideoGenScreen() {
  const { productionPlan, videoTimeline, setVideoTimeline, videoResult, setVideoResult, navigate } = useApp()
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
  }, [])

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

  const switchMode = (m) => { setMode(m); runGeneration(m) }

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
    await new Promise(r => setTimeout(r, 800))
    setTimeline((prev) => prev.map((s) => s.id === editForm.id ? { ...editForm } : s))
    if (selected?.id === editForm.id) setSelected({ ...editForm })
    setUpdating(false)
    setEditModal(false)
  }

  const swapAsset = async (asset) => {
    setAssetModal(false)
    setRegenerating(true)
    await regenerateVisual({ sceneId: selected.id })
    setTimeline((prev) => prev.map((s) => s.id === selected.id ? { ...s, visual: asset.label } : s))
    setSelected((s) => s ? { ...s, visual: asset.label } : s)
    setRegenerating(false)
  }

  const creatorPhotoUrl = (name) =>
    photoRun?.libraryId && name ? photoUrl(`/assets/${photoRun.libraryId}/file/${encodeURIComponent(name)}`) : null

  // ── Creator photos: upload + review ─────────────────────────────────────────
  if (phase === 'setup') {
    return (
      <CreatorPhotosStep plan={productionPlan} mode={mode} review={review} setReview={setReview}
        choices={choices} setChoices={setChoices} onGenerate={startFromPhotos} />
    )
  }

  // ── Generating ──────────────────────────────────────────────────────────────
  if (phase === 'generating') {
    return (
      <Page>
        <div className="max-w-md mx-auto mt-10">
          <Card className="p-8">
            <div className="flex items-center gap-3 mb-6">
              <Sparkles size={20} className="text-purple-400 animate-pulse" />
              <h2 className="text-discord-white font-bold">Generating AI Video…</h2>
            </div>
            <ProgressSteps steps={VIDEO_STEPS} currentStep={step} />
            {stepDetail && !error && (
              <p className="text-discord-muted text-xs mt-3 truncate">{stepDetail}</p>
            )}
            {error ? (
              <Alert type="error" className="mt-4">
                <p>{error}</p>
                <Btn size="sm" variant="secondary" icon={RefreshCw} className="mt-2" onClick={() => runGeneration()}>Try again</Btn>
              </Alert>
            ) : (
              <Alert type="info" className="mt-4">
                {mode === 'personalised' ? 'Personalised' : 'Generic baseline'} edit · voiceover → shots → assets → FFmpeg render. Takes a few minutes on the GPU.
              </Alert>
            )}
          </Card>
        </div>
      </Page>
    )
  }

  // ── Done ────────────────────────────────────────────────────────────────────
  return (
    <Page>
      <div className="max-w-4xl mx-auto">
        <div className="flex items-start justify-between mb-6 flex-wrap gap-3">
          <SectionHeader icon={Sparkles} title="AI Video Preview" subtitle="Structured timeline — click any scene to inspect and edit." />
          <div className="flex gap-2">
            <div className="flex rounded-lg overflow-hidden border border-discord-faint/30">
              {['personalised', 'generic'].map((m) => (
                <button key={m} onClick={() => mode !== m && switchMode(m)}
                  className={`px-3 py-1.5 text-xs font-semibold ${mode === m ? 'bg-discord-blurple text-white' : 'bg-discord-sidebar text-discord-muted hover:text-discord-white'}`}>
                  {m === 'personalised' ? 'Personalised' : 'Generic'}
                </button>
              ))}
            </div>
            <Btn variant="secondary" size="sm" icon={Images} onClick={() => setPhase('setup')}>Your photos</Btn>
            <Btn variant="secondary" size="sm" icon={RefreshCw} onClick={() => runGeneration()}>Regenerate</Btn>
            <Btn size="sm" icon={ChevronRight} onClick={() => navigate('publish')}>Continue to Publish</Btn>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
          {/* Video player (real MP4 from the backend, mock preview otherwise) */}
          <div className="lg:col-span-3">
            <div className="bg-black rounded-2xl overflow-hidden aspect-[9/16] max-h-[420px] flex flex-col items-center justify-center relative border border-discord-faint/20">
              {videoResult?.videoUrl ? (
                <video ref={videoRef} src={videoResult.videoUrl} controls playsInline className="w-full h-full object-contain" />
              ) : selected ? (
                <>
                  <div className="absolute inset-0 flex items-center justify-center"
                    style={{ backgroundColor: selected.thumbnailBg + '22' }}>
                    <div className="text-center px-6">
                      <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-3"
                        style={{ backgroundColor: selected.thumbnailBg }}>
                        <Play size={28} className="text-white ml-1" />
                      </div>
                      <p className="text-white font-bold text-sm">{selected.segment}</p>
                      <p className="text-white/70 text-xs mt-1">{selected.startTime} — {selected.endTime}</p>
                    </div>
                  </div>
                  {/* Caption overlay */}
                  <div className="absolute bottom-8 left-4 right-4 text-center">
                    <p className="text-white font-bold text-sm bg-black/60 rounded-lg px-3 py-1.5 inline-block">
                      {selected.caption}
                    </p>
                  </div>
                </>
              ) : (
                <div className="text-center px-6">
                  <Play size={40} className="text-discord-faint mb-3 mx-auto" />
                  <p className="text-discord-muted text-sm">Select a scene to preview</p>
                </div>
              )}
            </div>

            {/* Voiceover text */}
            {selected && (
              <Card className="mt-3 p-3 animate-fadeIn">
                <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide mb-1">Voiceover</p>
                <p className="text-discord-text text-xs leading-relaxed">{selected.voiceover}</p>
              </Card>
            )}
          </div>

          {/* Timeline */}
          <div className="lg:col-span-2 space-y-2">
            <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide mb-3">Timeline</p>
            {timeline.map((scene) => (
              <button
                key={scene.id}
                onClick={() => selectScene(scene)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all
                  ${selected?.id === scene.id ? 'bg-discord-blurple/20 border border-discord-blurple/40' : 'bg-discord-sidebar border border-discord-faint/20 hover:border-discord-faint/50'}`}
              >
                {creatorPhotoUrl(creatorShot(scene)?.assetName) ? (
                  <img src={creatorPhotoUrl(creatorShot(scene).assetName)} alt=""
                    className="w-10 h-10 rounded-lg object-cover flex-shrink-0" />
                ) : (
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 text-white text-xs font-bold"
                    style={{ backgroundColor: scene.thumbnailBg }}>
                    {scene.startTime.replace('00:', '')}
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-discord-white text-xs font-semibold truncate">{scene.segment}</p>
                  <p className="text-discord-muted text-xs">{scene.startTime} – {scene.endTime}</p>
                  {sceneSources(scene) && (
                    <p className={`text-[10px] truncate ${creatorShot(scene) ? 'text-discord-green' : 'text-discord-muted'}`}>
                      {sceneSources(scene)}
                    </p>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Measured evaluation (pipeline/video/evaluator.py) */}
        {videoResult?.evaluation?.scores && (
          <Card className="mt-5 p-4 animate-fadeIn">
            <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide mb-3">
              Measured style fidelity · {videoResult.mode}
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              <Score label="Style fidelity" value={pct(videoResult.evaluation.scores.style_fidelity)} />
              <Score label="Visual look match" value={pct(videoResult.evaluation.scores.visual_match)}
                hint={videoResult.evaluation.visual
                  ? `CLIP ${videoResult.evaluation.visual.creator_similarity} vs creator's own ${videoResult.evaluation.visual.creator_self_similarity}`
                  : 'no Module 2 visual vectors'} />
              <Score label="Cut pacing match" value={pct(videoResult.evaluation.scores.pacing_match)}
                hint={`${videoResult.evaluation.measured?.avg_shot_duration ?? '—'}s vs ${videoResult.evaluation.target?.avg_shot_duration ?? '—'}s`} />
              <Score label="Speech rate match" value={pct(videoResult.evaluation.scores.speech_rate_match)}
                hint={`${videoResult.evaluation.measured?.speech_rate_wpm ?? '—'} vs ${videoResult.evaluation.target?.speech_rate_wpm ?? '—'} wpm`} />
              <Score label="CLIP alignment" value={videoResult.evaluation.clip_alignment?.mean?.toFixed(3) ?? '—'}
                hint={Object.entries(videoResult.evaluation.asset_sources || {}).map(([k, v]) => `${v} ${k}`).join(' · ')} />
            </div>
          </Card>
        )}

        {/* Scene actions */}
        {selected && (
          <Card className="mt-5 p-4 animate-fadeIn">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <p className="text-discord-white font-semibold text-sm">{selected.segment}</p>
                <p className="text-discord-muted text-xs">{selected.visual}</p>
              </div>
              <div className="flex gap-2 flex-wrap">
                <Btn variant="secondary" size="sm" icon={Edit2} onClick={() => openEdit(selected)}>Edit Scene</Btn>
                <Btn variant="secondary" size="sm" icon={RefreshCw} loading={regenerating} onClick={() => setAssetModal(true)}>
                  {regenerating ? 'Regenerating…' : 'Swap Visual'}
                </Btn>
              </div>
            </div>
            {selected.shots?.length > 0 && (
              <div className="mt-3 space-y-1">
                <p className="text-discord-muted text-[11px] font-semibold uppercase tracking-wide">Shots</p>
                {selected.shots.map((sh, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    {sh.source === 'creator' && creatorPhotoUrl(sh.assetName)
                      ? <img src={creatorPhotoUrl(sh.assetName)} alt="" className="w-7 h-7 rounded object-cover" />
                      : <div className="w-7 h-7 rounded bg-discord-input" />}
                    <Badge color={sh.source === 'creator' ? 'green' : 'muted'}>{SOURCE_LABEL[sh.source] || sh.source}</Badge>
                    <span className="text-discord-muted truncate flex-1">{sh.query}</span>
                    <span className="text-discord-muted">
                      {sh.source === 'creator'
                        ? `SigLIP ${sh.assetScore?.toFixed(3) ?? '—'}`
                        : sh.clipScore !== null && sh.clipScore !== undefined ? `CLIP ${sh.clipScore.toFixed(3)}` : ''}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {updating && (
              <div className="mt-3 text-center text-discord-muted text-xs animate-pulse">
                Updating timeline… Re-rendering preview…
              </div>
            )}
          </Card>
        )}
      </div>

      {/* Edit scene modal */}
      <Modal open={editModal} onClose={() => setEditModal(false)} title="Edit Scene" width="max-w-lg">
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Input label="Start time" value={editForm.startTime || ''} onChange={(e) => setEditForm(f => ({ ...f, startTime: e.target.value }))} />
            <Input label="End time"   value={editForm.endTime   || ''} onChange={(e) => setEditForm(f => ({ ...f, endTime:   e.target.value }))} />
          </div>
          <Textarea label="Subtitle / Voiceover" value={editForm.voiceover || ''} onChange={(e) => setEditForm(f => ({ ...f, voiceover: e.target.value }))} rows={3} />
          <Input label="Caption overlay" value={editForm.caption || ''} onChange={(e) => setEditForm(f => ({ ...f, caption: e.target.value }))} />
          <div className="flex gap-3">
            <Btn className="flex-1" onClick={saveEdit} loading={updating}>Save</Btn>
            <Btn variant="secondary" onClick={() => setEditModal(false)}>Cancel</Btn>
          </div>
        </div>
      </Modal>

      {/* Asset swap modal */}
      <Modal open={assetModal} onClose={() => setAssetModal(false)} title="Choose Visual Asset">
        <div className="space-y-2">
          {MOCK_VISUAL_ASSETS.map((a) => (
            <button
              key={a.id}
              onClick={() => swapAsset(a)}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg bg-discord-input hover:bg-discord-hover text-left transition-colors"
            >
              <div className="w-8 h-8 rounded flex-shrink-0" style={{ backgroundColor: a.color }} />
              <span className="text-discord-white text-sm">{a.label}</span>
            </button>
          ))}
        </div>
      </Modal>
    </Page>
  )
}

function Score({ label, value, hint }) {
  return (
    <div className="bg-discord-sidebar rounded-lg px-3 py-2">
      <p className="text-discord-muted text-[11px]">{label}</p>
      <p className="text-discord-white font-bold text-lg">{value}</p>
      {hint && <p className="text-discord-muted text-[10px] truncate">{hint}</p>}
    </div>
  )
}
