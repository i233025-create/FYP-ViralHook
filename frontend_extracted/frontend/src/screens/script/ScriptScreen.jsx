import { useState, useEffect } from 'react'
import { RotateCcw, Edit2, AlertTriangle, ArrowRight, ArrowLeft, Check, X, PenLine } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { generateScripts, buildProductionPlan } from '../../services/api'
import {
  Btn, Card, Badge, ScoreBar, Page, PageHero, ActionBar, Alert, Modal, Textarea,
  SegmentTag, InfoTip,
} from '../../components/ui'
import JobProgress from '../../components/JobProgress'
import { CountUp, Stagger, StaggerItem } from '../../components/motion'
import { MOCK_SCRIPT_VARIANTS } from '../../data/mockData'

const GEN_STEPS = [
  { id: 1, label: 'Retrieving your past videos' },
  { id: 2, label: 'Writing script variants' },
  { id: 3, label: 'Scoring hooks' },
  { id: 4, label: 'Checking structure' },
  { id: 5, label: 'Measuring style consistency' },
  { id: 6, label: 'Selecting candidates' },
]
const PASS = 70

// How each score is measured (docs/UI_WORKFLOW.md §7). Shown in ⓘ tooltips.
const HOW = {
  style: 'How close the sentence length, use of "you" and share of questions are to your own past videos. — if we have no transcripts of yours yet.',
  hook: 'An AI judge answers 6 fixed questions about the opening line (keeps you watching, specific, concrete, promises a benefit, matches the hook type, sayable in ~3 s). It is checked first against a deliberately weak hook.',
  structure: 'Share of structure checks passed: 5 scenes in order, ends at ~0:30, a real hook, short captions, no repeated scenes, nothing copied from your past videos.',
  timing: 'Spoken words vs what fits 30 seconds at your speaking speed: full marks within ±15%.',
  overall: 'The average of the scores that could be measured. 70% or more passes.',
}

const passed = (v) => v.overall != null && v.overall >= PASS
// Hooks sometimes arrive already wrapped in quotes
const unquote = (t = '') => t.trim().replace(/^["“”']+|["“”']+$/g, '')
/** Hook in two parts for the two-colour quote: first sentence, then the rest (or two halves). */
function splitHook(text) {
  const sentences = text.match(/[^.!?]+[.!?]*\s*/g) || [text]
  if (sentences.length > 1) return [sentences[0].trim(), sentences.slice(1).join('').trim()]
  const words = text.split(/\s+/)
  if (words.length < 6) return [text, '']
  const mid = Math.ceil(words.length / 2)
  return [words.slice(0, mid).join(' '), words.slice(mid).join(' ')]
}

export default function ScriptScreen() {
  const { selectedTopic, setSelectedVariant, setProductionPlan, navigate, creatorProfile } = useApp()
  const [phase, setPhase] = useState('generating') // generating | results | failed | error
  const [step, setStep] = useState(0)
  const [variants, setVariants] = useState([])
  const [selected, setSelected] = useState(null)
  const [editTarget, setEditTarget] = useState(null)
  const [editedHook, setEditedHook] = useState('')
  const [buildingPlan, setBuildingPlan] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => { runGeneration() }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  const runGeneration = async () => {
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
        creatorProfile,
        onStep: (s) => setStep(s.id - 1),
      })
      setVariants(v)
      // Start on the best-scoring variant; the creator can switch freely
      setSelected([...v].sort((a, b) => (b.overall ?? -1) - (a.overall ?? -1))[0] || null)
      setPhase(failed ? 'failed' : 'results')
    } catch (err) {
      setVariants([])
      setPhase('error')
      setErrorMsg(err?.message || 'Script generation failed. Check that the backend server is running.')
    }
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

  const saveHook = () => {
    const updated = { ...editTarget, hook: editedHook }
    setVariants((prev) => prev.map((v) => (v.id === editTarget.id ? updated : v)))
    if (selected?.id === editTarget.id) setSelected(updated)
    setEditTarget(null)
  }

  const hero = (lead, aside) => (
    <PageHero step="02" label="Scripting" title={['Script', 'Variants']} topic={selectedTopic?.topic} lead={lead} aside={aside} />
  )

  // ── Generating ──────────────────────────────────────────────────────────────
  if (phase === 'generating') {
    return (
      <Page art="script">
        {hero('Writing three scripts in your voice and measuring each one. This takes about a minute.')}
        <JobProgress icon={PenLine} title="Writing your scripts" steps={GEN_STEPS} currentStep={step}
          hint="Three variants in your voice, each scored on style, hook, structure and timing." />
      </Page>
    )
  }

  // ── Backend error ───────────────────────────────────────────────────────────
  if (phase === 'error') {
    return (
      <Page art="script">
        {hero('Something went wrong while writing your scripts.')}
        <div className="max-w-xl space-y-4">
          <Alert type="error">{errorMsg}</Alert>
          <div className="flex gap-2">
            <Btn icon={RotateCcw} onClick={runGeneration}>Try again</Btn>
            <Btn variant="ghost" icon={ArrowLeft} onClick={() => navigate('topic-select')}>Change topic</Btn>
          </div>
        </div>
      </Page>
    )
  }

  // ── No variant passed ───────────────────────────────────────────────────────
  if (phase === 'failed') {
    return (
      <Page art="script">
        {hero('None of the variants reached the quality bar. Regenerate, change the topic, or edit one by hand.')}
        <Card className="max-w-2xl p-6">
          <div className="mb-4 flex items-center gap-2 text-sm font-medium text-vh-strong">
            <AlertTriangle size={16} className="text-vh-warn" /> No candidate scored {PASS}% or more
          </div>
          <ul className="divide-y divide-vh-line/10 rounded-lg border border-vh-edge/25">
            {variants.map((v) => (
              <li key={v.id} className="flex items-center justify-between px-4 py-3 text-sm">
                <span className="text-vh-text">{v.label}</span>
                <span className="font-semibold text-vh-bad tabular">{v.overall ?? '—'}%</span>
              </li>
            ))}
          </ul>
          {variants[0]?.failReason && (
            <div className="mt-4"><Alert type="warning"><span className="font-medium">Example issue:</span> {variants[0].failReason}</Alert></div>
          )}
          <div className="mt-6 flex flex-wrap gap-2">
            <Btn icon={RotateCcw} onClick={runGeneration}>Regenerate</Btn>
            <Btn variant="secondary" icon={ArrowLeft} onClick={() => navigate('topic-select')}>Change topic</Btn>
            <Btn variant="ghost" icon={Edit2} onClick={() => {
              const v = MOCK_SCRIPT_VARIANTS(selectedTopic?.topic)
              setVariants(v); setSelected(v[0]); setPhase('results')
            }}>Edit manually</Btn>
          </div>
        </Card>
      </Page>
    )
  }

  // ── Results ─────────────────────────────────────────────────────────────────
  const topPickId = [...variants].sort((a, b) => (b.overall ?? -1) - (a.overall ?? -1))[0]?.id
  const totalDuration = selected?.scenes?.length ? selected.scenes[selected.scenes.length - 1].endTime || '0:30' : '0:30'
  const [hookA, hookB] = splitHook(unquote(selected?.hook || ''))

  return (
    <Page art="script">
      {hero(
        <>{variants.length} scripts written in your own voice for “{selectedTopic?.topic}”. Every score below is measured — hover the info icons to see how.</>,
      )}

      {/* Variant tabs */}
      <Stagger role="tablist" aria-label="Script variants" className="grid gap-5 sm:grid-cols-3">
        {variants.map((v) => {
          const on = selected?.id === v.id
          const ok = passed(v)
          return (
            <StaggerItem as="button" key={v.id} type="button" role="tab" aria-selected={on} onClick={() => setSelected(v)}
              className={`min-w-0 w-full rounded-2xl border-2 border-vh-night bg-white p-5 text-left transition-[transform,box-shadow] duration-200
                ${on ? 'shadow-accent' : 'hover:-translate-y-0.5 hover:shadow-hard-sm'}`}>
              <div className="flex items-start justify-between gap-3">
                <span className="flex flex-wrap items-center gap-2 pt-1">
                  <span className="font-mono text-[13px] font-semibold uppercase tracking-[0.06em]">{v.label}</span>
                  {v.id === topPickId && <span className="rounded bg-vh-accent2 px-1.5 py-0.5 font-mono text-[12px] font-bold text-white">Top pick</span>}
                </span>
                <span className={`display text-[3rem] leading-[0.85] tabular ${ok ? '' : 'text-vh-accent2'}`}>
                  <CountUp value={v.overall ?? '—'} />%
                </span>
              </div>
              <p className="mt-3 truncate text-[15px] font-bold">{v.hookType}{v.structure ? ` · ${v.structure}` : ''}</p>
              <p className={`mt-1.5 flex items-center gap-1 text-[15px] font-medium ${ok ? '' : 'text-vh-accent2'}`}>
                {ok ? <Check size={15} strokeWidth={3} /> : <X size={15} strokeWidth={3} />}
                {ok ? (on ? 'Passed · selected' : 'Passed') : `Below ${PASS}%${on ? ' · selected' : ''}`}
              </p>
            </StaggerItem>
          )
        })}
      </Stagger>

      {/* Selected variant: the hook on a black panel */}
      {selected && (
        <Card tone="dark" className="mt-9 p-6 sm:p-9">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex min-w-0 max-w-full flex-wrap gap-2">
              <Badge color="accent" size="md" className="max-w-full"><span className="truncate">{selected.hookType}</span></Badge>
              {selected.structure && (
                <Badge color="steel" size="md" className="max-w-full"><span className="truncate" title={selected.structure}>{selected.structure}</span></Badge>
              )}
            </div>
            <div className="flex items-center gap-5 text-[15px] font-semibold">
              <button type="button" onClick={() => { setEditTarget(selected); setEditedHook(selected.hook) }}
                className="text-vh-accent underline underline-offset-4 hover:text-vh-accent-hover">Edit hook</button>
              <span className="group relative flex items-center gap-1 underline underline-offset-4">
                How is this scored? <InfoTip text={HOW.overall} />
              </span>
            </div>
          </div>

          <blockquote className="display mt-7 text-[clamp(2rem,4.4vw,3.6rem)] leading-[1.02]">
            <span className="text-vh-cream">“{hookA}</span>
            {hookB && <span className="text-vh-accent"> {hookB}</span>}
            <span className={hookB ? 'text-vh-accent' : 'text-vh-cream'}>”</span>
          </blockquote>

          <div className="mt-9 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <ScoreBar label="Style consistency" value={selected.styleConsistency} hint={HOW.style} />
            <ScoreBar label="Hook alignment" value={selected.hookAlignment} hint={HOW.hook} />
            <ScoreBar label="Structure" value={selected.structureAlignment} hint={HOW.structure} />
            <ScoreBar label="Timing fit" value={selected.timingFit} hint={HOW.timing} />
          </div>

          {selected.feedback?.length > 0 && (
            <ul className="mt-7 space-y-1.5">
              {selected.feedback.slice(0, 4).map((f, i) => (
                <li key={i} className="flex items-start gap-2 text-[15px] leading-relaxed">
                  <AlertTriangle size={15} className="mt-0.5 shrink-0 text-vh-accent" />{f}
                </li>
              ))}
            </ul>
          )}
          {!selected.feedback?.length && passed(selected) && (
            <p className="mt-7 flex items-center gap-2 text-[16px]">
              <Check size={17} strokeWidth={3} /> No issues found by the evaluator.
            </p>
          )}
        </Card>
      )}

      {/* Scenes */}
      {selected?.scenes?.length > 0 && (
        <Card shadow={false} as="section" className="mt-10 overflow-hidden">
          <header className="flex flex-wrap items-center justify-between gap-2 border-b-2 border-vh-night px-5 py-4 sm:px-8">
            <h2 className="display text-[2.2rem]">{selected.scenes.length} scenes · {totalDuration}</h2>
            <span className="font-mono text-[13px]">Full script of {selected.label.toLowerCase()}</span>
          </header>
          <Stagger as="ol" gap={0.05} className="divide-y divide-vh-night/15">
            {selected.scenes.map((sc, i) => (
              <StaggerItem as="li" key={i} className="grid gap-2 px-5 py-4 transition-colors hover:bg-vh-cream/60 sm:grid-cols-[9.5rem_9.5rem_1fr] sm:items-center sm:gap-4 sm:px-8">
                {/* phones: time + segment on one line, text below; wider: three columns */}
                <div className="flex items-center gap-3 sm:contents">
                  <span className="font-mono text-[13px]">{sc.startTime}{sc.endTime ? `–${sc.endTime}` : ''}</span>
                  <span><SegmentTag segment={sc.segment} /></span>
                </div>
                <p className="text-[16px] font-medium leading-relaxed">{sc.voiceover}</p>
              </StaggerItem>
            ))}
          </Stagger>
        </Card>
      )}

      <ActionBar actions={<>
        <Btn variant="secondary" icon={RotateCcw} onClick={runGeneration}>Regenerate</Btn>
        <Btn size="lg" onClick={proceed} loading={buildingPlan} disabled={!selected} iconRight={ArrowRight}>
          {buildingPlan ? 'Building plan…' : 'Continue to plan'}
        </Btn>
      </>}>
        {selected ? (
          <div>
            <p className="flex items-center gap-1.5 text-lg font-bold">
              {passed(selected) ? <Check size={19} strokeWidth={3} /> : <AlertTriangle size={17} className="text-vh-accent" />}
              {selected.label.replace('VARIANT', 'Variant')} selected · {selected.overall ?? '—'}%
            </p>
            <p className="mt-0.5 text-[15px]">You can still edit every scene in the next step.</p>
          </div>
        ) : <p className="text-[15px]">Choose a variant</p>}
      </ActionBar>

      <Modal open={!!editTarget} onClose={() => setEditTarget(null)} title={`Edit hook · ${editTarget?.label || ''}`}>
        <Textarea label="Hook" value={editedHook} onChange={(e) => setEditedHook(e.target.value)} rows={4}
          hint="Scores were measured on the original hook; they update when you regenerate." />
        <div className="mt-5 flex justify-end gap-2">
          <Btn variant="ghost" onClick={() => setEditTarget(null)}>Cancel</Btn>
          <Btn onClick={saveHook}>Save hook</Btn>
        </div>
      </Modal>
    </Page>
  )
}
