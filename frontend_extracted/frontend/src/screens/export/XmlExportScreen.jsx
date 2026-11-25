import { useState } from 'react'
import { FileCode, Download, ArrowRight, ArrowLeft, Check, Minus } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { exportXML } from '../../services/api'
import { Btn, Card, Page, PageHero, Alert, ActionBar, Stat, Tile } from '../../components/ui'
import JobProgress from '../../components/JobProgress'
import { MOCK_XML_SUMMARY } from '../../data/mockData'
import { TimelinePreview } from '../../components/previews'

const EXPORT_STEPS = [
  { id: 1, label: 'Preparing timeline' },
  { id: 2, label: 'Mapping clips' },
  { id: 3, label: 'Building tracks' },
  { id: 4, label: 'Adding timestamps' },
  { id: 5, label: 'Adding captions' },
  { id: 6, label: 'Generating XML' },
]

export default function XmlExportScreen() {
  const { productionPlan, setExportXML, selectedTopic, navigate } = useApp()
  const [phase, setPhase] = useState('idle')  // idle | generating | done
  const [step, setStep] = useState(-1)
  const [xml, setXml] = useState(null)
  const [error, setError] = useState('')

  const startExport = async () => {
    setPhase('generating')
    setStep(0)
    setError('')
    try {
      const { xml: x } = await exportXML({ plan: productionPlan, onStep: (s) => setStep(s.id - 1) })
      setXml(x)
      setExportXML(x)
      setPhase('done')
    } catch (err) {
      setError(err?.message || 'XML export failed. Check that the backend is running.')
      setPhase('idle')
    }
  }

  const fileName = `${(productionPlan?.title || 'viralhook').replace(/\s+/g, '_')}.xml`
  const downloadXML = () => {
    const url = URL.createObjectURL(new Blob([xml], { type: 'application/xml' }))
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    a.click()
    URL.revokeObjectURL(url)
  }

  const s = MOCK_XML_SUMMARY
  const contents = [
    ['Timeline', s.timeline], [`${s.clips} clips`, true], ['Timestamps', s.timestamps], ['Clip ordering', s.clipOrdering],
    ['Trims / cuts', s.trimsAndCuts], ['Captions', s.captions], [`${s.audioTracks} audio track`, true], [s.transitions, true],
  ]

  return (
    <Page art="xml">
      <PageHero
        step="04"
        label="Output"
        title={['Premiere', 'Project']}
        topic={selectedTopic?.topic}
        lead="An XML timeline you import into Adobe Premiere Pro and finish with your own footage."
      />

      {error && <Alert type="error" className="mb-6 max-w-3xl">{error}</Alert>}

      {phase === 'idle' && (
        <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <Card className="p-6 sm:p-8">
            <p className="font-mono text-[13px] font-bold uppercase tracking-[0.1em] text-vh-accent2">Ready to export</p>
            <h2 className="display mt-3 text-[clamp(2.2rem,3.6vw,3rem)]">{productionPlan?.title || 'Your plan'}</h2>
            <div className="relative mt-5 h-36 overflow-hidden rounded-xl border-2 border-vh-night bg-vh-cream">
              <TimelinePreview scenes={productionPlan?.scenes || []} />
            </div>
            <dl className="mt-5 grid grid-cols-3 gap-3">
              <Tile label="Scenes" value={productionPlan?.scenes?.length ?? '—'} />
              <Tile label="Duration" value={productionPlan?.totalDuration || '—'} />
              <Tile label="Tracks" value="V1 · V2 · A1" />
            </dl>
            <Btn size="lg" icon={FileCode} className="mt-7" onClick={startExport}>Generate XML</Btn>
          </Card>
          <TracksPanel />
        </div>
      )}

      {phase === 'generating' && (
        <JobProgress icon={FileCode} title="Building your Premiere project" steps={EXPORT_STEPS} currentStep={step}
          hint="Usually done in a few seconds." />
      )}

      {phase === 'done' && (
        <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <Card className="p-6 sm:p-8">
            <p className="font-mono text-[13px] font-bold uppercase tracking-[0.1em] text-vh-accent2">Project ready</p>
            <p className="display mt-3 break-all text-[clamp(1.9rem,3vw,2.5rem)]">{fileName}</p>
            <ul className="mt-6 grid grid-cols-2 gap-3">
              {contents.map(([label, ok]) => (
                <li key={label} className={`flex items-center gap-2 rounded-lg bg-vh-cream px-3 py-2.5 text-[15px] font-semibold ${ok ? '' : 'line-through decoration-2'}`}>
                  {ok ? <Check size={16} strokeWidth={3} /> : <Minus size={16} />}{label}
                </li>
              ))}
            </ul>
            <Btn size="lg" icon={Download} className="mt-7" onClick={downloadXML}>Download XML</Btn>
          </Card>
          <Card tone="dark" className="p-6 sm:p-8">
            <p className="font-mono text-[13px] font-semibold uppercase tracking-[0.08em] text-vh-accent">Next</p>
            <h2 className="display mt-3 text-[2.6rem]">Import into Premiere Pro</h2>
            <ol className="mt-5 space-y-4">
              {['File → Import → choose the .xml file.', 'V1 holds colour placeholders — replace them with your footage.', 'V2 is the caption layer, A1 the voiceover slots.'].map((t, i) => (
                <li key={t} className="flex gap-4">
                  <span className="display w-9 shrink-0 text-[2rem] leading-none text-vh-accent">{String(i + 1).padStart(2, '0')}</span>
                  <span className="text-[16px] leading-relaxed">{t}</span>
                </li>
              ))}
            </ol>
          </Card>
        </div>
      )}

      <ActionBar actions={<>
        <Btn variant="secondary" icon={ArrowLeft} onClick={() => navigate('output')}>Other output</Btn>
        <Btn size="lg" iconRight={ArrowRight} disabled={phase !== 'done'} onClick={() => navigate('publish')}>Continue to publish</Btn>
      </>}>
        <Stat label="Scenes" value={productionPlan?.scenes?.length ?? '—'} />
        <Stat label="Duration" value={productionPlan?.totalDuration || '—'} />
        <Stat label="Format" value="Premiere XML" />
      </ActionBar>
    </Page>
  )
}

/** Black panel: what each track of the exported timeline holds. */
function TracksPanel() {
  const tracks = [
    ['V2', 'Captions', 'Short caption per scene, timed to the voiceover'],
    ['V1', 'Clips', 'Colour placeholders in scene order, trimmed to length'],
    ['A1', 'Voice', 'One voiceover slot per scene'],
  ]
  return (
    <Card tone="dark" className="p-6 sm:p-8">
      <p className="font-mono text-[13px] font-semibold uppercase tracking-[0.08em] text-vh-accent">What's inside</p>
      <h2 className="display mt-3 text-[2.6rem]">Three tracks, ready</h2>
      <ul className="mt-5 space-y-3">
        {tracks.map(([id, name, text]) => (
          <li key={id} className="flex items-start gap-4 rounded-xl bg-vh-frame px-4 py-3">
            <span className="display w-9 shrink-0 text-[2rem] leading-none text-vh-accent">{id}</span>
            <div>
              <p className="text-[16px] font-bold">{name}</p>
              <p className="text-[14px]">{text}</p>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}
