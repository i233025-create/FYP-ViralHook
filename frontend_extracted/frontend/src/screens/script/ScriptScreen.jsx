import { useState, useEffect } from 'react'
import { FileText, RotateCcw, ChevronDown, ChevronUp, Edit2, Check, X, AlertTriangle, ChevronRight } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { generateScripts, buildProductionPlan } from '../../services/api'
import {
  Btn, Card, Badge, ScoreBar, ProgressSteps, SectionHeader,
  Page, Alert, Modal, Textarea,
} from '../../components/ui'
import { MOCK_SCRIPT_VARIANTS } from '../../data/mockData'

const GEN_STEPS = [
  { id: 1, label: 'Retrieving creator context' },
  { id: 2, label: 'Generating script variants' },
  { id: 3, label: 'Evaluating hooks' },
  { id: 4, label: 'Evaluating structure' },
  { id: 5, label: 'Checking creator style consistency' },
  { id: 6, label: 'Selecting candidates' },
]

export default function ScriptScreen() {
  const { selectedTopic, setSelectedVariant, setProductionPlan, navigate, creatorProfile } = useApp()
  const [phase, setPhase] = useState('generating') // generating | results | failed | error
  const [step, setStep] = useState(0)
  const [variants, setVariants] = useState([])
  const [selected, setSelected] = useState(null)
  const [editTarget, setEditTarget] = useState(null)
  const [editedHook, setEditedHook] = useState('')
  const [buildingPlan, setBuildingPlan] = useState(false)
  const [genCount, setGenCount] = useState(0)
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => { runGeneration() }, [])

  const runGeneration = async (forceFail = false) => {
    setPhase('generating')
    setStep(0)
    setSelected(null)
    setVariants([])
    try {
      const { failed, variants: v } = await generateScripts({
        topic: selectedTopic?.topic,
        // Research card → scripting context (why it trends, angle, real evidence).
        // Own ideas have no research behind them, so no trend is sent.
        trend: selectedTopic?.evidence ? {
          why_trending: selectedTopic.signals?.[0] || '',
          suggested_angle: selectedTopic.whyThis || '',
          evidence: selectedTopic.evidence,
        } : null,
        creatorProfile: creatorProfile,
        forceFail: forceFail,
        onStep: (s) => setStep(s.id - 1),
      })
      setVariants(v)
      setPhase(failed ? 'failed' : 'results')
    } catch (err) {
      // Show error clearly so we know backend failed — no silent mock fallback
      setVariants([])
      setPhase('error')
      setErrorMsg(err?.message || 'Script generation failed. Check that the backend server is running.')
    }
    setGenCount((c) => c + 1)
  }

  const proceed = async () => {
    if (!selected) return
    setBuildingPlan(true)
    setSelectedVariant(selected)
    const { plan } = await buildProductionPlan(selected)
    setProductionPlan(plan)
    setBuildingPlan(false)
    navigate('production')
  }

  // ── Generating ──────────────────────────────────────────────────────────────
  if (phase === 'generating') {
    return (
      <Page>
        <div className="max-w-md mx-auto mt-10">
          <Card className="p-8">
            <div className="flex items-center gap-3 mb-6">
              <FileText size={20} className="text-discord-blurple animate-pulse" />
              <h2 className="text-discord-white font-bold">Generating script variants…</h2>
            </div>
            {selectedTopic && (
              <p className="text-discord-muted text-xs mb-5 bg-discord-input rounded-lg px-3 py-2">
                Topic: <span className="text-discord-white">{selectedTopic.topic}</span>
              </p>
            )}
            <ProgressSteps steps={GEN_STEPS} currentStep={step} />
          </Card>
        </div>
      </Page>
    )
  }

  // ── Error (backend failure) ─────────────────────────────────────────────────
  if (phase === 'error') {
    return (
      <Page>
        <div className="max-w-xl mx-auto mt-10 animate-fadeIn">
          <Card className="p-8 border-discord-red/30">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-discord-red/15 flex items-center justify-center">
                <AlertTriangle size={20} className="text-discord-red" />
              </div>
              <div>
                <h2 className="text-discord-white font-bold">Backend error</h2>
                <p className="text-discord-muted text-xs">Script generation failed — make sure the server is running.</p>
              </div>
            </div>
            <div className="bg-discord-input rounded-lg px-3 py-2.5 mb-6">
              <p className="text-discord-red text-xs font-mono">{errorMsg}</p>
            </div>
            <Btn icon={RotateCcw} onClick={() => runGeneration(false)}>Try Again</Btn>
          </Card>
        </div>
      </Page>
    )
  }

  // ── Failed ──────────────────────────────────────────────────────────────────
  if (phase === 'failed') {
    return (
      <Page>
        <div className="max-w-xl mx-auto mt-10 animate-fadeIn">
          <Card className="p-8 border-discord-red/30">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-discord-red/15 flex items-center justify-center">
                <AlertTriangle size={20} className="text-discord-red" />
              </div>
              <div>
                <h2 className="text-discord-white font-bold">No candidates met the quality threshold</h2>
                <p className="text-discord-muted text-xs">All generated variants scored below the minimum quality bar.</p>
              </div>
            </div>

            <div className="space-y-2 mb-6">
              {variants.map((v) => (
                <div key={v.id} className="flex items-center justify-between px-3 py-2 bg-discord-input rounded-lg">
                  <span className="text-discord-white text-xs font-semibold">{v.label}</span>
                  <span className="text-discord-red text-xs font-bold">{v.overall}% — below threshold</span>
                </div>
              ))}
            </div>

            {variants[0]?.failReason && (
              <Alert type="warning">
                <span className="font-semibold">Example issue:</span> {variants[0].failReason}
              </Alert>
            )}

            <div className="grid grid-cols-2 gap-3 mt-6">
              <Btn variant="secondary" onClick={() => runGeneration(false)} icon={RotateCcw}>Regenerate</Btn>
              <Btn variant="secondary" onClick={() => runGeneration(false)} icon={RotateCcw}>Try Again</Btn>
              <Btn variant="ghost" onClick={() => navigate('topic-select')}>← Change Topic</Btn>
              <Btn
                variant="outline"
                onClick={() => {
                  setPhase('results')
                  setVariants(MOCK_SCRIPT_VARIANTS(selectedTopic?.topic))
                }}
              >
                Edit Manually
              </Btn>
            </div>
          </Card>
        </div>
      </Page>
    )
  }

  // ── Results ─────────────────────────────────────────────────────────────────
  return (
    <Page>
      <div className="max-w-2xl mx-auto">
        <div className="flex items-start justify-between mb-6 flex-wrap gap-3">
          <SectionHeader
            icon={FileText}
            title="Script Variants"
            subtitle={`${variants.length} candidates generated for: "${selectedTopic?.topic}"`}
          />
          <Btn variant="secondary" size="sm" icon={RotateCcw} onClick={() => runGeneration(false)}>
            Regenerate
          </Btn>
        </div>

        <div className="space-y-4 mb-6">
          {variants.map((v) => (
            <VariantCard
              key={v.id}
              variant={v}
              selected={selected?.id === v.id}
              onSelect={() => setSelected(v)}
              onEdit={() => { setEditTarget(v); setEditedHook(v.hook) }}
            />
          ))}
        </div>

        {/* Demo: trigger fail state */}
        {genCount <= 1 && (
          <div className="mb-4 text-center">
            <button onClick={() => runGeneration(true)} className="text-discord-faint text-xs hover:text-discord-muted underline transition-colors">
              Demo: show failure state →
            </button>
          </div>
        )}

        {selected && (
          <div className="animate-fadeIn">
            <div className="bg-discord-blurple/10 border border-discord-blurple/30 rounded-xl p-4 mb-4">
              <p className="text-discord-blurple text-xs font-semibold mb-1">Selected</p>
              <p className="text-discord-white text-sm font-medium">{selected.label} — Overall {selected.overall}%</p>
            </div>
            <Btn size="lg" className="w-full" onClick={proceed} loading={buildingPlan} icon={ChevronRight}>
              {buildingPlan ? 'Building Production Plan…' : 'Continue to Production Plan'}
            </Btn>
          </div>
        )}
      </div>

      {/* Edit modal */}
      <Modal open={!!editTarget} onClose={() => setEditTarget(null)} title={`Edit ${editTarget?.label}`}>
        <p className="text-discord-muted text-xs mb-3">Editing the hook. After saving, scores will be recalculated.</p>
        <Textarea
          label="Hook"
          value={editedHook}
          onChange={(e) => setEditedHook(e.target.value)}
          rows={4}
        />
        <div className="flex gap-3 mt-4">
          <Btn className="flex-1" onClick={() => {
            setVariants((prev) => prev.map((v) => v.id === editTarget.id ? { ...v, hook: editedHook } : v))
            setEditTarget(null)
          }}>
            Save Changes
          </Btn>
          <Btn variant="secondary" onClick={() => setEditTarget(null)}>Cancel</Btn>
        </div>
      </Modal>
    </Page>
  )
}

function VariantCard({ variant: v, selected, onSelect, onEdit }) {
  const [expanded, setExpanded] = useState(false)
  const isPassing = v.overall >= 70

  return (
    <Card selected={selected} className="overflow-hidden">
      <div className="p-5">
        {/* Header row */}
        <div className="flex items-start gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="text-discord-white font-bold text-sm">{v.label}</span>
              <Badge color={isPassing ? 'green' : 'red'}>{v.overall}% overall</Badge>
              <Badge color="purple">{v.hookType}</Badge>
            </div>
            <p className="text-discord-muted text-xs">{v.structure}</p>
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <Btn variant="ghost" size="sm" icon={Edit2} onClick={onEdit}>Edit</Btn>
            <Btn size="sm" variant={selected ? 'primary' : 'secondary'} onClick={onSelect}>
              {selected ? '✓ Selected' : 'Select'}
            </Btn>
          </div>
        </div>

        {/* Hook preview */}
        <div className="bg-discord-input border-l-4 border-discord-blurple rounded-lg px-4 py-3 mb-4">
          <p className="text-discord-muted text-xs font-semibold uppercase tracking-wide mb-1">Hook</p>
          <p className="text-discord-white text-sm italic whitespace-pre-line">{v.hook}</p>
        </div>

        {/* Scores */}
        <div className="space-y-2">
          <ScoreBar label="Style Consistency" value={v.styleConsistency} />
          <ScoreBar label="Hook Alignment"    value={v.hookAlignment} />
          <ScoreBar label="Structure Align."  value={v.structureAlignment} />
          {v.timingFit !== undefined && <ScoreBar label="Timing Fit" value={v.timingFit} />}
        </div>

        {/* Expand toggle */}
        <button
          onClick={() => setExpanded(e => !e)}
          className="flex items-center gap-1 mt-3 text-discord-blurple text-xs hover:underline"
        >
          {expanded ? <><ChevronUp size={14} /> Hide scenes</> : <><ChevronDown size={14} /> Preview {v.scenes?.length} scenes</>}
        </button>
      </div>

      {/* Scenes */}
      {expanded && v.scenes && (
        <div className="border-t border-discord-faint/20 px-5 pb-5 pt-3 space-y-2 animate-fadeIn">
          {v.scenes.map((sc, i) => (
            <div key={i} className="flex gap-3 bg-discord-input rounded-lg px-3 py-2.5">
              <span className="text-discord-blurple font-mono text-xs font-bold flex-shrink-0 w-12">{sc.startTime}</span>
              <div className="border-l border-discord-faint/30 pl-3 min-w-0">
                <p className="text-discord-yellow text-xs font-semibold mb-0.5">{sc.segment}</p>
                <p className="text-discord-text text-xs leading-relaxed">{sc.voiceover}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
