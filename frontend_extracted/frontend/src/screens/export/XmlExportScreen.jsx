import { useState } from 'react'
import { FileCode, Download, CheckCircle, ChevronRight } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { exportXML } from '../../services/api'
import { Btn, Card, ProgressSteps, SectionHeader, Page, Alert } from '../../components/ui'
import { MOCK_XML_SUMMARY } from '../../data/mockData'

const EXPORT_STEPS = [
  { id: 1, label: 'Preparing timeline' },
  { id: 2, label: 'Mapping clips' },
  { id: 3, label: 'Building tracks' },
  { id: 4, label: 'Adding timestamps' },
  { id: 5, label: 'Adding captions' },
  { id: 6, label: 'Generating XML' },
]

export default function XmlExportScreen() {
  const { productionPlan, setExportXML, navigate } = useApp()
  const [phase, setPhase] = useState('idle')  // idle | generating | done
  const [step, setStep] = useState(-1)
  const [xml, setXml] = useState(null)

  const startExport = async () => {
    setPhase('generating')
    setStep(0)
    const { xml: x } = await exportXML({
      plan: productionPlan,
      onStep: (s) => setStep(s.id - 1),
    })
    setXml(x)
    setExportXML(x)
    setPhase('done')
  }

  const downloadXML = () => {
    const blob = new Blob([xml], { type: 'application/xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${(productionPlan?.title || 'viralhook').replace(/\s+/g, '_')}.xml`
    a.click()
    URL.revokeObjectURL(url)
  }

  const s = MOCK_XML_SUMMARY

  return (
    <Page>
      <div className="max-w-xl mx-auto">
        <SectionHeader icon={FileCode} title="XML Export" subtitle="Export your production plan as an Adobe Premiere Pro project." />

        {/* Plan summary */}
        {phase === 'idle' && (
          <Card className="p-6 mb-4 animate-fadeIn">
            <h3 className="text-discord-white font-semibold mb-3">Production Plan Ready</h3>
            <p className="text-discord-muted text-sm mb-1">{productionPlan?.title}</p>
            <p className="text-discord-muted text-xs mb-4">{productionPlan?.scenes?.length} scenes · {productionPlan?.totalDuration}</p>
            <Btn size="lg" className="w-full" icon={FileCode} onClick={startExport}>
              Generate XML
            </Btn>
          </Card>
        )}

        {/* Generating */}
        {phase === 'generating' && (
          <Card className="p-8 animate-fadeIn">
            <div className="flex items-center gap-3 mb-6">
              <FileCode size={20} className="text-discord-blurple animate-pulse" />
              <h3 className="text-discord-white font-semibold">Building XML project…</h3>
            </div>
            <ProgressSteps steps={EXPORT_STEPS} currentStep={step} />
          </Card>
        )}

        {/* Done */}
        {phase === 'done' && (
          <div className="animate-fadeIn space-y-4">
            <Card className="p-6 border-discord-green/30">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-full bg-discord-green/15 flex items-center justify-center">
                  <CheckCircle size={20} className="text-discord-green" />
                </div>
                <div>
                  <h3 className="text-discord-white font-bold">XML Project Ready</h3>
                  <p className="text-discord-green text-xs">All tracks generated successfully</p>
                </div>
              </div>

              {/* Contents checklist */}
              <div className="grid grid-cols-2 gap-2 mb-5">
                {[
                  ['Timeline', s.timeline],
                  [`${s.clips} clips`, true],
                  ['Timestamps', s.timestamps],
                  ['Clip ordering', s.clipOrdering],
                  ['Trims / cuts', s.trimsAndCuts],
                  ['Captions', s.captions],
                  [`${s.audioTracks} audio track`, true],
                  [s.transitions, true],
                ].map(([label, ok]) => (
                  <div key={label} className={`flex items-center gap-2 text-xs ${ok ? 'text-discord-text' : 'text-discord-faint line-through'}`}>
                    <CheckCircle size={12} className={ok ? 'text-discord-green' : 'text-discord-faint'} />
                    {label}
                  </div>
                ))}
              </div>

              <Btn size="lg" className="w-full" icon={Download} onClick={downloadXML}>
                Download XML
              </Btn>
            </Card>

            <Alert type="info">
              <span className="font-semibold">Importing into Premiere Pro:</span> File → Import → select the .xml file. V1 = colour placeholder clips (replace with footage), V2 = caption layers, A1 = voiceover slots.
            </Alert>

            <Btn variant="secondary" className="w-full" icon={ChevronRight} onClick={() => navigate('publish')}>
              Continue to Publish
            </Btn>
          </div>
        )}
      </div>
    </Page>
  )
}
