import { useState, useRef } from 'react'
import { TrendingUp, Upload, Film, X, CheckCircle, ArrowLeft, Info } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { processCreatorVideos } from '../../services/api'
import { Btn, Input, Select, Alert, ProgressSteps, Badge, SectionHeader } from '../../components/ui'
import { NICHES } from '../../data/mockData'

const PROCESS_STEPS = [
  { id: 1, label: 'Uploading videos' },
  { id: 2, label: 'Extracting transcripts' },
  { id: 3, label: 'Building creator knowledge base' },
  { id: 4, label: 'Analysing creator style patterns' },
  { id: 5, label: 'Generating creator profile' },
]

export default function ExperiencedCreatorScreen() {
  const { setCreatorProfile, navigate } = useApp()
  const fileRef = useRef(null)
  const [handle, setHandle] = useState('')
  const [niche, setNiche] = useState(NICHES[0])
  const [videos, setVideos] = useState([])
  const [phase, setPhase] = useState('form') // 'form' | 'processing' | 'done'
  const [currentStep, setCurrentStep] = useState(-1)
  const [profile, setProfile] = useState(null)
  const [error, setError] = useState('')

  const addVideos = (files) => {
    const valid = Array.from(files).filter((f) => f.type.startsWith('video/'))
    if (!valid.length) { setError('Please upload video files only.'); return }
    setError('')
    setVideos((v) => [...v, ...valid.map((f) => ({ id: crypto.randomUUID(), name: f.name, size: f.size }))])
  }

  const removeVideo = (id) => setVideos((v) => v.filter((x) => x.id !== id))

  const fmt = (b) => b < 1e6 ? `${(b / 1024).toFixed(0)} KB` : `${(b / 1e6).toFixed(1)} MB`

  const startProcessing = async () => {
    if (!handle.trim()) { setError('Please enter your social handle.'); return }
    if (videos.length === 0) { setError('Please upload at least one video.'); return }
    setError('')
    setPhase('processing')
    setCurrentStep(0)
    try {
      const { profile: p } = await processCreatorVideos({
        handle, niche,
        onStep: (step) => setCurrentStep(step.id - 1),
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

  // ── DONE state ──────────────────────────────────────────────────────────────
  if (phase === 'done' && profile) {
    return (
      <div className="flex h-screen w-screen bg-discord-dark items-center justify-center p-6 overflow-y-auto">
        <div className="w-full max-w-lg animate-fadeIn">
          <div className="bg-discord-sidebar border border-discord-green/30 rounded-2xl p-6 mb-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-discord-green/20 flex items-center justify-center">
                <CheckCircle size={20} className="text-discord-green" />
              </div>
              <div>
                <h2 className="text-discord-white font-bold text-lg">Creator Profile Generated</h2>
                <p className="text-discord-green text-xs">{profile.analyzedVideos} videos analysed</p>
              </div>
            </div>


            <div className="mt-4 space-y-3">
              <Row label="Handle" value={profile.handle} />
              <Row label="Niche" value={profile.niche} />
              <Row label="Dominant Hook" value={<Badge color="purple">{profile.dominantHookType}</Badge>} />
              <Row label="Structure" value={<Badge color="blurple">{profile.dominantStructure}</Badge>} />
              <div>
                <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide mb-1">Style Summary</p>
                <p className="text-discord-text text-sm leading-relaxed bg-discord-input rounded-lg px-3 py-2.5">
                  {profile.styleSummary}
                </p>
              </div>
            </div>
          </div>
          <Btn size="lg" className="w-full" onClick={finish}>
            Go to Dashboard
          </Btn>
        </div>
      </div>
    )
  }

  // ── PROCESSING state ────────────────────────────────────────────────────────
  if (phase === 'processing') {
    return (
      <div className="flex h-screen w-screen bg-discord-dark items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="bg-discord-sidebar border border-discord-faint/25 rounded-2xl p-8">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-discord-blurple/15 flex items-center justify-center">
                <TrendingUp size={20} className="text-discord-blurple animate-pulse" />
              </div>
              <div>
                <h2 className="text-discord-white font-bold">Processing videos</h2>
                <p className="text-discord-muted text-xs">{videos.length} video{videos.length !== 1 ? 's' : ''} queued</p>
              </div>
            </div>
            <ProgressSteps steps={PROCESS_STEPS} currentStep={currentStep} />
            <p className="text-discord-faint text-xs mt-6 text-center">This may take a moment…</p>
          </div>
        </div>
      </div>
    )
  }

  // ── FORM state ──────────────────────────────────────────────────────────────
  return (
    <div className="flex h-screen w-screen bg-discord-dark items-center justify-center p-6 overflow-y-auto">
      <div className="w-full max-w-lg">
        <button onClick={() => navigate('creator-type')} className="flex items-center gap-1.5 text-discord-muted hover:text-discord-white text-sm mb-6 transition-colors">
          <ArrowLeft size={16} /> Back
        </button>

        <SectionHeader
          icon={TrendingUp}
          title="Upload your videos"
          subtitle="We'll analyse your existing content to extract your unique creator style."
        />

        <div className="space-y-4 bg-discord-sidebar border border-discord-faint/25 rounded-2xl p-6">
          <div className="grid grid-cols-2 gap-4">
            <Input label="Social handle" value={handle} onChange={(e) => setHandle(e.target.value)} placeholder="@yourhandle" required />
            <Select label="Primary niche" value={niche} onChange={(e) => setNiche(e.target.value)} options={NICHES} />
          </div>

          {/* Drop zone */}
          <div
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); addVideos(e.dataTransfer.files) }}
            className="flex flex-col items-center justify-center border-2 border-dashed border-discord-faint/40 hover:border-discord-blurple/60 rounded-xl p-8 cursor-pointer transition-colors bg-discord-input/30 hover:bg-discord-blurple/5"
          >
            <input ref={fileRef} type="file" accept="video/*" multiple onChange={(e) => addVideos(e.target.files)} className="hidden" />
            <Upload size={24} className="text-discord-muted mb-2" />
            <p className="text-discord-white text-sm font-medium">Drop videos or click to browse</p>
            <p className="text-discord-muted text-xs mt-1">MP4, MOV, AVI — up to 10 videos</p>
          </div>

          {/* Video list */}
          {videos.length > 0 && (
            <div className="space-y-1.5">
              {videos.map((v) => (
                <div key={v.id} className="flex items-center gap-3 px-3 py-2 bg-discord-input rounded-lg group">
                  <Film size={14} className="text-discord-blurple flex-shrink-0" />
                  <span className="flex-1 text-discord-white text-xs truncate">{v.name}</span>
                  <span className="text-discord-muted text-xs">{fmt(v.size)}</span>
                  <button onClick={() => removeVideo(v.id)} className="opacity-0 group-hover:opacity-100 text-discord-muted hover:text-discord-red transition-all">
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {error && <Alert type="error">{error}</Alert>}

          <Btn size="lg" className="w-full" onClick={startProcessing} disabled={!videos.length || !handle}>
            Analyse My Videos
          </Btn>
        </div>
      </div>
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div className="flex items-start gap-3">
      <span className="text-discord-muted text-xs font-semibold uppercase tracking-wide w-28 flex-shrink-0 pt-0.5">{label}</span>
      <span className="text-discord-white text-sm">{value}</span>
    </div>
  )
}
