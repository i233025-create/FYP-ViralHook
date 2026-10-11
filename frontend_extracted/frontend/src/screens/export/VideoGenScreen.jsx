import { useState, useEffect } from 'react'
import { Sparkles, CheckCircle, Clock, Edit2, RefreshCw, ChevronRight, Play } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { generateAIVideo, regenerateVisual } from '../../services/api'
import { Btn, Card, Badge, ProgressSteps, SectionHeader, Page, Modal, Input, Textarea, Alert } from '../../components/ui'
import { MOCK_VISUAL_ASSETS } from '../../data/mockData'

const VIDEO_STEPS = [
  { id: 1, label: 'Processing production plan', done: true },
  { id: 2, label: 'Generating visual assets', done: true },
  { id: 3, label: 'Building JSON timeline', done: true },
  { id: 4, label: 'Rendering video' },
]

export default function VideoGenScreen() {
  const { productionPlan, videoTimeline, setVideoTimeline, navigate } = useApp()
  const [phase, setPhase] = useState('generating')
  const [step, setStep] = useState(0)
  const [timeline, setTimeline] = useState(videoTimeline || [])
  const [selected, setSelected] = useState(null)
  const [editModal, setEditModal] = useState(false)
  const [editForm, setEditForm] = useState({})
  const [updating, setUpdating] = useState(false)
  const [assetModal, setAssetModal] = useState(false)
  const [regenerating, setRegenerating] = useState(false)

  useEffect(() => {
    if (videoTimeline && phase !== 'done') {
      setTimeline(videoTimeline); setPhase('done'); return
    }
    runGeneration()
  }, [])

  const runGeneration = async () => {
    setPhase('generating')
    setStep(0)
    const { timeline: t } = await generateAIVideo({
      plan: productionPlan,
      onStep: (s) => setStep(s.id - 1),
    })
    setTimeline(t)
    setVideoTimeline(t)
    setPhase('done')
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
            <Alert type="info" className="mt-4">
              <span className="font-semibold">Prototype:</span> This is a frontend prototype. The final system will use a JSON timeline → FFmpeg rendering pipeline to produce an MP4.
            </Alert>
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
            <Btn variant="secondary" size="sm" icon={RefreshCw} onClick={runGeneration}>Regenerate</Btn>
            <Btn size="sm" icon={ChevronRight} onClick={() => navigate('publish')}>Continue to Publish</Btn>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
          {/* Mock video player */}
          <div className="lg:col-span-3">
            <div className="bg-black rounded-2xl overflow-hidden aspect-[9/16] max-h-[420px] flex flex-col items-center justify-center relative border border-discord-faint/20">
              {selected ? (
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
                onClick={() => setSelected(scene)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all
                  ${selected?.id === scene.id ? 'bg-discord-blurple/20 border border-discord-blurple/40' : 'bg-discord-sidebar border border-discord-faint/20 hover:border-discord-faint/50'}`}
              >
                <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 text-white text-xs font-bold"
                  style={{ backgroundColor: scene.thumbnailBg }}>
                  {scene.startTime.replace('00:', '')}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-discord-white text-xs font-semibold truncate">{scene.segment}</p>
                  <p className="text-discord-muted text-xs">{scene.startTime} – {scene.endTime}</p>
                </div>
              </button>
            ))}
          </div>
        </div>

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
