import { useState } from 'react'
import { Clapperboard, Edit2, Check, ChevronRight, Plus } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { Btn, Card, Badge, SectionHeader, Page, Modal, Input, Textarea } from '../../components/ui'

export default function ProductionScreen() {
  const { productionPlan, setProductionPlan, navigate } = useApp()
  const [editScene, setEditScene] = useState(null)
  const [editForm, setEditForm] = useState({})

  if (!productionPlan) return null

  const openEdit = (scene) => {
    setEditScene(scene)
    setEditForm({ ...scene })
  }

  const saveEdit = () => {
    setProductionPlan((prev) => ({
      ...prev,
      scenes: prev.scenes.map((s) => s.id === editForm.id ? { ...editForm } : s),
    }))
    setEditScene(null)
  }

  const setF = (k) => (e) => setEditForm((f) => ({ ...f, [k]: e.target.value }))

  const SEGMENT_COLORS = {
    HOOK: 'blurple', SETUP: 'green', 'MAIN POINT': 'yellow',
    EVIDENCE: 'red', CONCLUSION: 'purple', CTA: 'purple',
    'BUILD-UP': 'green', REVEAL: 'yellow', FRAMEWORK: 'cyan',
    CONFLICT: 'yellow', 'TURNING POINT': 'green', LESSON: 'blurple',
  }

  return (
    <Page>
      <div className="max-w-3xl mx-auto">
        <div className="flex items-start justify-between mb-6 flex-wrap gap-3">
          <SectionHeader
            icon={Clapperboard}
            title="Production Plan"
            subtitle={`${productionPlan.scenes?.length || 0} scenes · Total: ${productionPlan.totalDuration}`}
          />
          <Btn size="lg" icon={ChevronRight} onClick={() => navigate('output')}>
            Continue to Export
          </Btn>
        </div>

        {/* Timeline */}
        <div className="relative">
          {/* Vertical line */}
          <div className="absolute left-[22px] top-0 bottom-0 w-px bg-discord-faint/30 z-0" />

          <div className="space-y-4">
            {productionPlan.scenes?.map((scene, i) => (
              <div key={scene.id} className="relative flex gap-4 animate-fadeIn" style={{ animationDelay: `${i * 0.05}s` }}>
                {/* Timeline dot */}
                <div className="flex-shrink-0 z-10 flex flex-col items-center">
                  <div className="w-11 h-11 rounded-full bg-discord-sidebar border-2 border-discord-blurple/50 flex items-center justify-center text-discord-blurple font-bold text-xs">
                    {String(i + 1).padStart(2, '0')}
                  </div>
                </div>

                <Card className="flex-1 p-5">
                  <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge color={SEGMENT_COLORS[scene.segment] || 'muted'}>{scene.segment}</Badge>
                      <span className="text-discord-muted text-xs font-mono">{scene.startTime} – {scene.endTime}</span>
                    </div>
                    <Btn variant="ghost" size="sm" icon={Edit2} onClick={() => openEdit(scene)}>Edit</Btn>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <SceneField label="Voiceover" value={scene.voiceover} multiline />
                    <SceneField label="Caption" value={scene.caption} />
                    <SceneField label="Shot Description" value={scene.shot} />
                    <SceneField label="Visual / B-Roll" value={scene.visual} />
                  </div>
                </Card>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-8">
          <Btn size="lg" className="w-full" icon={ChevronRight} onClick={() => navigate('output')}>
            Continue to Export / Video
          </Btn>
        </div>
      </div>

      {/* Edit modal */}
      <Modal open={!!editScene} onClose={() => setEditScene(null)} title={`Edit Scene — ${editForm.segment}`} width="max-w-2xl">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Input label="Start time" value={editForm.startTime || ''} onChange={setF('startTime')} placeholder="00:00" />
            <Input label="End time"   value={editForm.endTime || ''}   onChange={setF('endTime')}   placeholder="00:05" />
          </div>
          <Textarea label="Voiceover" value={editForm.voiceover || ''} onChange={setF('voiceover')} rows={3} />
          <Input label="Caption overlay" value={editForm.caption || ''} onChange={setF('caption')} placeholder="CAPTION TEXT" />
          <Input label="Shot description" value={editForm.shot || ''} onChange={setF('shot')} placeholder="e.g. Close-up talking head" />
          <Textarea label="Visual / B-Roll suggestion" value={editForm.visual || ''} onChange={setF('visual')} rows={2} />
          <div className="flex gap-3">
            <Btn className="flex-1" icon={Check} onClick={saveEdit}>Save</Btn>
            <Btn variant="secondary" onClick={() => setEditScene(null)}>Cancel</Btn>
          </div>
        </div>
      </Modal>
    </Page>
  )
}

function SceneField({ label, value, multiline = false }) {
  return (
    <div className="bg-discord-input rounded-lg px-3 py-2.5">
      <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-discord-text text-xs leading-relaxed ${multiline ? '' : 'truncate'}`}>{value}</p>
    </div>
  )
}
